from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import sqrt
import time
from uuid import uuid4

from sqlalchemy import MetaData, Table, bindparam, func, inspect, or_, select, text
from sqlalchemy.exc import DBAPIError

from trading_ai.institutional_options.models import (
    InstitutionalDecisionSnapshotModel,
    InstitutionalOpportunityModel,
)
from trading_ai.institutional_options.trade_builder_authority import (
    certified_ready_opportunity_ids,
)
from .models import (
    PortfolioCorrelationSnapshotModel,
    PortfolioDecisionIntelligenceModel,
    PortfolioIntelligencePublicationModel,
)
from trading_ai.institutional_options.publication_scope import latest_stock_scanner_run_id
from .service import PortfolioRiskAllocationService, clamp, number


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DecisionGenerationCoverageError(RuntimeError):
    """Raised when a decision generation cannot cover its governed source set."""


class InstitutionalDecisionIntelligenceService:
    """Canonical portfolio-aware decision layer for M64 and future intelligence modules."""

    POLICY_VERSION = "M64-DECISION-INTELLIGENCE-1.0"
    # PostgreSQL performs lifecycle mutation and SHA-256 hashing inside the
    # database.  A 500-row batch keeps row locks and WAL bounded while avoiding
    # the 5,000+ client round trips that made M64.2.3 take more than 100 minutes.
    STALE_RETIREMENT_BATCH_SIZE = 500
    STALE_RETIREMENT_STATEMENT_TIMEOUT_MS = 120_000
    STALE_RETIREMENT_LOCK_TIMEOUT_MS = 5_000
    STALE_RETIREMENT_TOTAL_TIMEOUT_SECONDS = 180.0
    HISTORY_CLEANUP_BATCH_SIZE = 1_000
    HISTORY_CLEANUP_STATEMENT_TIMEOUT_MS = 120_000
    HISTORY_CLEANUP_LOCK_TIMEOUT_MS = 5_000
    HISTORY_CLEANUP_WORK_BUDGET_SECONDS = 180.0
    HISTORY_CLEANUP_MIN_BATCH_BUDGET_SECONDS = 20.0
    HISTORY_CLEANUP_FINALIZATION_RESERVE_SECONDS = 10.0
    HISTORY_CLEANUP_MIN_STATEMENT_TIMEOUT_MS = 10_000
    QUERY_CANCELED_SQLSTATE = "57014"

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.risk_service = PortfolioRiskAllocationService(session_factory)

    def compact_non_authoritative_history(
        self,
        portfolio_id: str = "PAPER-PRIMARY",
        *,
        progress=None,
    ) -> dict:
        """Resumably retire rows that are not part of the active publication.

        Historical cleanup is intentionally separate from the final authority
        transaction. Each batch commits independently, but the risk snapshot
        referenced by current_portfolio_allocation is always excluded. A
        failed or interrupted cleanup therefore cannot invalidate the current
        publication, and the next invocation resumes from committed progress.
        """
        with self.session_factory() as session:
            publication = session.scalar(
                select(PortfolioIntelligencePublicationModel).where(
                    PortfolioIntelligencePublicationModel.portfolio_id == portfolio_id,
                    PortfolioIntelligencePublicationModel.publication_name
                    == "current_portfolio_allocation",
                )
            )
            dialect_name = (
                session.bind.dialect.name
                if session.bind is not None
                else "unknown"
            )
            if publication is None or not publication.risk_snapshot_id:
                return {
                    "status": "SKIPPED_NO_CURRENT_PUBLICATION",
                    "complete": True,
                    "retired": 0,
                    "remaining": 0,
                    "batch_count": 0,
                }
            authoritative_risk_snapshot_id = str(publication.risk_snapshot_id)
            publication_payload = dict(publication.payload_json or {})
            authoritative_stock_run_id = publication_payload.get(
                "stock_scanner_run_id"
            )

        if dialect_name != "postgresql":
            return {
                "status": "SKIPPED_NON_POSTGRESQL",
                "complete": True,
                "retired": 0,
                "remaining": 0,
                "batch_count": 0,
                "authoritative_risk_snapshot_id": authoritative_risk_snapshot_id,
            }

        statement = text("""
            WITH candidates AS (
                SELECT
                    decision_intelligence_id,
                    (
                        COALESCE(payload_json::jsonb, '{}'::jsonb)
                        || jsonb_build_object(
                            'lifecycle',
                            COALESCE(payload_json::jsonb -> 'lifecycle', '{}'::jsonb)
                            || jsonb_build_object(
                                'status', 'SUPERSEDED',
                                'superseded_at', CAST(:superseded_at AS text),
                                'superseded_by_risk_snapshot_id',
                                    CAST(:authoritative_risk_snapshot_id AS text),
                                'superseded_by_stock_scanner_run_id',
                                    CAST(:authoritative_stock_run_id AS text),
                                'retirement_reason',
                                    'NON_AUTHORITATIVE_HISTORY_COMPACTION',
                                'state_hash_algorithm',
                                    'POSTGRESQL_JSONB_CANONICAL_SHA256_V1'
                            )
                        )
                    ) AS next_payload
                FROM portfolio_decision_intelligence_snapshots
                WHERE portfolio_id = :portfolio_id
                  AND risk_snapshot_id <> :authoritative_risk_snapshot_id
                  AND COALESCE(
                        payload_json::jsonb #>> '{lifecycle,status}',
                        ''
                      ) <> 'SUPERSEDED'
                  AND (
                        CAST(:cursor AS text) IS NULL
                        OR decision_intelligence_id > CAST(:cursor AS text)
                      )
                ORDER BY decision_intelligence_id
                LIMIT :batch_size
                FOR UPDATE
            ), updated AS (
                UPDATE portfolio_decision_intelligence_snapshots AS target
                SET
                    payload_json = CAST(candidates.next_payload AS json),
                    state_hash = encode(
                        sha256(convert_to(candidates.next_payload::text, 'UTF8')),
                        'hex'
                    )
                FROM candidates
                WHERE target.decision_intelligence_id =
                      candidates.decision_intelligence_id
                RETURNING target.decision_intelligence_id
            )
            SELECT
                COUNT(*) AS updated_count,
                MIN(decision_intelligence_id) AS first_decision_id,
                MAX(decision_intelligence_id) AS last_decision_id
            FROM updated
        """)
        started = time.monotonic()
        stamp = utc_now()
        cursor: str | None = None
        retired = 0
        batch_number = 0
        complete = False
        deferred_reason: str | None = None
        if progress:
            progress("historical_decision_cleanup_started", {
                "portfolio_id": portfolio_id,
                "authoritative_risk_snapshot_id": authoritative_risk_snapshot_id,
                "batch_size": self.HISTORY_CLEANUP_BATCH_SIZE,
                "work_budget_seconds": self.HISTORY_CLEANUP_WORK_BUDGET_SECONDS,
                "execution_mode": "POSTGRESQL_RESUMABLE_COMMITTED_JSONB",
            })

        while True:
            elapsed = time.monotonic() - started
            remaining_budget = (
                self.HISTORY_CLEANUP_WORK_BUDGET_SECONDS - elapsed
            )
            if remaining_budget <= self.HISTORY_CLEANUP_MIN_BATCH_BUDGET_SECONDS:
                deferred_reason = "WORK_BUDGET_BOUNDARY"
                break
            statement_timeout_ms = min(
                self.HISTORY_CLEANUP_STATEMENT_TIMEOUT_MS,
                max(
                    self.HISTORY_CLEANUP_MIN_STATEMENT_TIMEOUT_MS,
                    int(
                        (
                            remaining_budget
                            - self.HISTORY_CLEANUP_FINALIZATION_RESERVE_SECONDS
                        )
                        * 1_000
                    ),
                ),
            )
            with self.session_factory() as session:
                try:
                    session.execute(text(
                        f"SET LOCAL lock_timeout = "
                        f"'{self.HISTORY_CLEANUP_LOCK_TIMEOUT_MS}ms'"
                    ))
                    session.execute(text(
                        f"SET LOCAL statement_timeout = "
                        f"'{statement_timeout_ms}ms'"
                    ))
                    result = session.execute(statement, {
                        "portfolio_id": portfolio_id,
                        "authoritative_risk_snapshot_id":
                            authoritative_risk_snapshot_id,
                        "authoritative_stock_run_id":
                            authoritative_stock_run_id,
                        "superseded_at": stamp,
                        "cursor": cursor,
                        "batch_size": self.HISTORY_CLEANUP_BATCH_SIZE,
                    }).one()
                    batch_rows = int(result.updated_count or 0)
                    first_decision_id = result.first_decision_id
                    last_decision_id = result.last_decision_id
                    session.commit()
                except DBAPIError as exc:
                    sqlstate = (
                        getattr(exc.orig, "pgcode", None)
                        or getattr(exc.orig, "sqlstate", None)
                    )
                    session.rollback()
                    if sqlstate != self.QUERY_CANCELED_SQLSTATE:
                        raise
                    deferred_reason = "POSTGRESQL_QUERY_CANCELED"
                    if progress:
                        progress(
                            "historical_decision_cleanup_batch_deferred",
                            {
                                "reason": deferred_reason,
                                "sqlstate": sqlstate,
                                "retired": retired,
                                "batch_count": batch_number,
                                "last_completed_cursor": cursor,
                                "statement_timeout_ms": statement_timeout_ms,
                                "elapsed_seconds": round(
                                    time.monotonic() - started,
                                    3,
                                ),
                            },
                        )
                    break
            if batch_rows == 0:
                complete = True
                break
            batch_number += 1
            retired += batch_rows
            cursor = str(last_decision_id)
            if progress:
                progress("historical_decision_cleanup_batch_committed", {
                    "batch": batch_number,
                    "batch_rows": batch_rows,
                    "retired": retired,
                    "first_decision_id": first_decision_id,
                    "last_decision_id": last_decision_id,
                    "authoritative_risk_snapshot_id":
                        authoritative_risk_snapshot_id,
                    "execution_mode": "POSTGRESQL_RESUMABLE_COMMITTED_JSONB",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                })

        with self.session_factory() as session:
            remaining = int(session.scalar(text("""
                SELECT COUNT(*)
                FROM portfolio_decision_intelligence_snapshots
                WHERE portfolio_id = :portfolio_id
                  AND risk_snapshot_id <> :authoritative_risk_snapshot_id
                  AND COALESCE(
                        payload_json::jsonb #>> '{lifecycle,status}',
                        ''
                      ) <> 'SUPERSEDED'
            """), {
                "portfolio_id": portfolio_id,
                "authoritative_risk_snapshot_id":
                    authoritative_risk_snapshot_id,
            }) or 0)
        complete = remaining == 0
        result = {
            "status": "COMPLETE" if complete else "INCOMPLETE_RETRYABLE",
            "complete": complete,
            "retired": retired,
            "remaining": remaining,
            "batch_count": batch_number,
            "authoritative_risk_snapshot_id":
                authoritative_risk_snapshot_id,
            "execution_mode": "POSTGRESQL_RESUMABLE_COMMITTED_JSONB",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "deferred_reason": deferred_reason if not complete else None,
        }
        if progress:
            progress(
                "historical_decision_cleanup_completed"
                if complete
                else "historical_decision_cleanup_deferred",
                result,
            )
        return result

    def build(
        self,
        portfolio_id: str = "PAPER-PRIMARY",
        opportunity_ids: list[str] | None = None,
        limit: int | None = None,
        *,
        risk_snapshot_id: str | None = None,
        require_complete: bool = True,
        progress=None,
    ):
        risk = self.risk_service.snapshot(portfolio_id, risk_snapshot_id)
        if risk is None and risk_snapshot_id is not None:
            raise LookupError(
                f"Pinned portfolio risk snapshot {risk_snapshot_id} was not found "
                f"for portfolio {portfolio_id}"
            )
        risk = risk or self.risk_service.build(portfolio_id)
        with self.session_factory() as session:
            # Serialize overlapping M64 decision-intelligence builds for the same
            # portfolio in PostgreSQL.  This complements the fit-assessment
            # duplicate recovery and prevents two schedulers/operators from
            # racing the same unique portfolio/opportunity/risk-snapshot rows.
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                acquired = bool(session.scalar(text(
                    "SELECT pg_try_advisory_xact_lock(hashtext(:lock_key))"
                ), {
                    "lock_key": f"trading_ai:m64_decision_intelligence:{portfolio_id}"
                }))
                if not acquired:
                    raise DecisionGenerationCoverageError(
                        f"M64 decision generation is already active for {portfolio_id}"
                    )
            current_stock_run_id = latest_stock_scanner_run_id(session)
            if current_stock_run_id is None:
                raise DecisionGenerationCoverageError(
                    "No materialized current Stock Intelligence run is available"
                )

            eligible_ids = sorted(certified_ready_opportunity_ids(
                session,
                stock_scanner_run_id=current_stock_run_id,
                opportunity_ids=opportunity_ids,
            ))
            full_scope = not opportunity_ids and limit is None
            if require_complete and full_scope and not eligible_ids:
                raise DecisionGenerationCoverageError(
                    f"Current Stock Intelligence run {current_stock_run_id} has no "
                    "READY_FOR_EXECUTION opportunities"
                )

            query = select(
                InstitutionalDecisionSnapshotModel,
                InstitutionalOpportunityModel,
            ).join(
                InstitutionalOpportunityModel,
                InstitutionalOpportunityModel.opportunity_id == InstitutionalDecisionSnapshotModel.opportunity_id,
            ).where(
                InstitutionalOpportunityModel.state == "READY_FOR_EXECUTION",
                InstitutionalOpportunityModel.stock_scanner_run_id == current_stock_run_id,
                InstitutionalOpportunityModel.opportunity_id.in_(eligible_ids),
            )
            if opportunity_ids:
                query = query.where(InstitutionalDecisionSnapshotModel.opportunity_id.in_(opportunity_ids))
            query = query.order_by(InstitutionalDecisionSnapshotModel.institutional_score.desc())
            if limit:
                query = query.limit(limit)
            source_rows = list(session.execute(query).all())
            source_ids = [str(row.opportunity_id) for row, _ in source_rows]
            if progress:
                progress("decision_generation_source_loaded", {
                    "eligible": len(eligible_ids),
                    "source_rows": len(source_rows),
                    "stock_scanner_run_id": current_stock_run_id,
                    "risk_snapshot_id": risk["snapshot_id"],
                })
            missing_source_ids = sorted(set(eligible_ids) - set(source_ids))
            if require_complete and full_scope and missing_source_ids:
                raise DecisionGenerationCoverageError(
                    f"{len(missing_source_ids)} of {len(eligible_ids)} current opportunities "
                    "lack an Institutional Options decision snapshot; no portfolio "
                    "decision generation was activated"
                )
            symbols = [str(opportunity.symbol or "").upper() for _, opportunity in source_rows]
            correlation = self._correlation_snapshot(session, portfolio_id, risk, symbols)
            assessments = []
            for assessment_index, (row, opportunity) in enumerate(source_rows, 1):
                payload = dict(row.payload_json or {})
                symbol = str(opportunity.symbol or payload.get("symbol") or payload.get("underlying", {}).get("symbol") or "UNKNOWN").upper()
                sector = str(payload.get("sector") or payload.get("underlying", {}).get("sector_context", {}).get("sector") or "UNKNOWN")
                capital = number(row.capital_required or payload.get("valuation", {}).get("capital", {}).get("capital_required"))
                expected_value = number(row.expected_value or payload.get("valuation", {}).get("expected_value"))
                probability = number(row.calibrated_probability or payload.get("valuation", {}).get("probability", {}).get("calibrated_probability"), .5)
                selected_contract = payload.get("selected_contract") or {}
                greeks = self._candidate_greeks(selected_contract)
                candidate = {
                    "candidate_id": row.opportunity_id,
                    "opportunity_id": row.opportunity_id,
                    "symbol": symbol,
                    "sector": sector,
                    "strategy": row.selected_strategy,
                    "capital_required": capital,
                    "maximum_loss": capital,
                    "unit_risk": max(capital, 1.0),
                    "expected_value": expected_value,
                    "probability": probability,
                }
                fit = self.risk_service.assess(
                    candidate,
                    portfolio_id,
                    risk_snapshot_id=risk["snapshot_id"],
                )
                corr = self._portfolio_correlation(symbol, correlation)
                marginal = self._marginal_impact(risk, capital, greeks, corr)
                capital_efficiency = clamp((expected_value / capital * 100) if capital else 0)
                diversification_benefit = clamp(100 - abs(corr) * 100)
                opportunity_pre_score = clamp(
                    .45 * number(row.institutional_score)
                    + .30 * fit["portfolio_fit_score"]
                    + .15 * capital_efficiency
                    + .10 * diversification_benefit
                )
                assessments.append({
                    "row": row, "payload": payload, "symbol": symbol, "sector": sector,
                    "fit": fit, "correlation": corr, "marginal": marginal,
                    "capital_efficiency": capital_efficiency,
                    "diversification_benefit": diversification_benefit,
                    "pre_score": opportunity_pre_score,
                })
                if progress and (
                    assessment_index == len(source_rows)
                    or assessment_index % 25 == 0
                ):
                    progress("decision_generation_assessment_progress", {
                        "completed": assessment_index,
                        "total": len(source_rows),
                        "risk_snapshot_id": risk["snapshot_id"],
                    })
            ordered = sorted(assessments, key=lambda item: item["pre_score"], reverse=True)
            best = ordered[0]["pre_score"] if ordered else 0.0
            publication = session.scalar(select(PortfolioIntelligencePublicationModel).where(
                PortfolioIntelligencePublicationModel.portfolio_id == portfolio_id,
                PortfolioIntelligencePublicationModel.publication_name == "current_portfolio_allocation",
            ))
            published_payload = dict(publication.payload_json or {}) if publication else {}
            already_authoritative = bool(
                publication
                and publication.risk_snapshot_id == risk["snapshot_id"]
                and published_payload.get("stock_scanner_run_id") == current_stock_run_id
            )
            generation_status = "CURRENT" if already_authoritative else "STAGED"
            results = []
            for rank, item in enumerate(ordered, 1):
                row = item["row"]
                opportunity_cost = clamp(100 - max(0, best - item["pre_score"]) * 4)
                final_score = clamp(.85 * item["pre_score"] + .15 * opportunity_cost)
                decision_governance = self._decision_evaluation(final_score, item["fit"], item["marginal"])
                decision = decision_governance["decision"]
                explanation = self._explain(item, opportunity_cost, decision, rank, decision_governance)
                canonical = {
                    "policy_version": self.POLICY_VERSION,
                    "symbol": item["symbol"],
                    "sector": item["sector"],
                    "strategy": row.selected_strategy,
                    "lifecycle": {
                        "status": generation_status,
                        "source_stock_scanner_run_id": current_stock_run_id,
                        "risk_snapshot_id": risk["snapshot_id"],
                        "generated_at": utc_now(),
                        "authority": (
                            "CURRENT_PORTFOLIO_ALLOCATION_PUBLICATION"
                            if already_authoritative
                            else "PENDING_CURRENT_PORTFOLIO_ALLOCATION_PUBLICATION"
                        ),
                    },
                    "decision_identity": {
                        "opportunity_id": row.opportunity_id,
                        "institutional_decision_snapshot_id": row.decision_snapshot_id,
                        "risk_snapshot_id": risk["snapshot_id"],
                        "portfolio_id": portfolio_id,
                    },
                    "scores": {
                        "institutional_score": number(row.institutional_score),
                        "portfolio_fit_score": item["fit"]["portfolio_fit_score"],
                        "capital_efficiency_score": item["capital_efficiency"],
                        "diversification_benefit_score": item["diversification_benefit"],
                        "opportunity_cost_score": opportunity_cost,
                        "final_portfolio_score": final_score,
                    },
                    "correlation": {"portfolio_correlation": item["correlation"], "snapshot_id": correlation["correlation_snapshot_id"]},
                    "portfolio_impact": item["marginal"],
                    "capital_allocation": {
                        "recommended_quantity": item["fit"]["recommended_quantity"],
                        "recommended_capital": item["fit"]["recommended_capital"],
                        "minimum_quantity": 1 if item["fit"]["recommended_quantity"] else 0,
                        "maximum_quantity": max(item["fit"]["recommended_quantity"], min(10, item["fit"]["recommended_quantity"] * 2)),
                        "risk_budget_snapshot_id": risk["snapshot_id"],
                    },
                    "ranking": {"rank": rank, "candidate_count": len(ordered)},
                    "decision": decision,
                    "decision_governance": decision_governance,
                    "portfolio_fit_assessment": item["fit"],
                    "explainability": explanation,
                    "future_extensions": {"inflection_intelligence": None, "option_valuation_intelligence": None, "learning_confidence": None},
                }
                state_hash = sha256(json.dumps(canonical, sort_keys=True, default=str).encode()).hexdigest()
                existing = session.scalar(select(PortfolioDecisionIntelligenceModel).where(
                    PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id,
                    PortfolioDecisionIntelligenceModel.opportunity_id == row.opportunity_id,
                    PortfolioDecisionIntelligenceModel.risk_snapshot_id == risk["snapshot_id"],
                ))
                if existing is None:
                    existing = PortfolioDecisionIntelligenceModel(
                        decision_intelligence_id="M64-DI-" + uuid4().hex.upper(),
                        portfolio_id=portfolio_id, opportunity_id=row.opportunity_id,
                        institutional_decision_snapshot_id=row.decision_snapshot_id,
                        risk_snapshot_id=risk["snapshot_id"], created_at=utc_now(),
                        portfolio_fit_score=item["fit"]["portfolio_fit_score"],
                        opportunity_cost_score=opportunity_cost, final_portfolio_score=final_score,
                        recommended_quantity=item["fit"]["recommended_quantity"],
                        recommended_capital=item["fit"]["recommended_capital"], decision=decision,
                        rank=rank, state_hash=state_hash, payload_json=canonical,
                    )
                    session.add(existing)
                else:
                    existing.portfolio_fit_score=item["fit"]["portfolio_fit_score"]
                    existing.opportunity_cost_score=opportunity_cost
                    existing.final_portfolio_score=final_score
                    existing.recommended_quantity=item["fit"]["recommended_quantity"]
                    existing.recommended_capital=item["fit"]["recommended_capital"]
                    existing.decision=decision; existing.rank=rank; existing.state_hash=state_hash; existing.payload_json=canonical
                # A newly generated risk/decision set is staged.  The optimizer
                # activates it and replaces the embedded handoff decision in the
                # same transaction that advances current_portfolio_allocation.
                # This preserves the previous complete authority while a new cycle
                # is still being built.
                if already_authoritative:
                    base_payload = dict(row.payload_json or {})
                    base_payload["portfolio_decision"] = canonical
                    row.payload_json = base_payload
                results.append(canonical)
                if progress and (rank == len(ordered) or rank % 25 == 0):
                    progress("decision_generation_materialization_progress", {
                        "completed": rank,
                        "total": len(ordered),
                        "risk_snapshot_id": risk["snapshot_id"],
                    })
            session.flush()
            generated_ids = {str(item["decision_identity"]["opportunity_id"]) for item in results}
            coverage_missing = sorted(set(eligible_ids) - generated_ids)
            if require_complete and full_scope and coverage_missing:
                raise DecisionGenerationCoverageError(
                    f"Portfolio decision generation covered {len(generated_ids)} of "
                    f"{len(eligible_ids)} current opportunities"
                )
            session.commit()
            return {
                "portfolio_id": portfolio_id,
                "risk_snapshot_id": risk["snapshot_id"],
                "stock_scanner_run_id": current_stock_run_id,
                "correlation_snapshot_id": correlation["correlation_snapshot_id"],
                "eligible": len(eligible_ids),
                "requested": len(source_rows),
                "built": len(results),
                "missing": coverage_missing,
                "coverage_pct": round(len(generated_ids) / len(eligible_ids) * 100, 4) if eligible_ids else 100.0,
                "authority_status": "CURRENT" if already_authoritative else ("STAGED_COMPLETE" if not coverage_missing else "PARTIAL"),
                "rankings": results,
            }

    def activate_generation(
        self,
        session,
        *,
        portfolio_id: str,
        risk_snapshot_id: str,
        stock_scanner_run_id: str,
        selected_opportunity_ids: set[str],
        optimization_proof: dict,
        progress=None,
    ) -> dict:
        """Atomically activate a complete generation and retire prior authority.

        The caller must publish ``current_portfolio_allocation`` in the same
        database transaction.  No old decision is superseded until exact current
        opportunity coverage has been proven.
        """
        latest_run_id = latest_stock_scanner_run_id(session)
        if latest_run_id != stock_scanner_run_id:
            raise DecisionGenerationCoverageError(
                "Stock Intelligence advanced during portfolio generation: "
                f"expected {stock_scanner_run_id}, observed {latest_run_id}"
            )
        eligible_ids = certified_ready_opportunity_ids(
            session,
            stock_scanner_run_id=stock_scanner_run_id,
        )
        rows = list(session.scalars(select(PortfolioDecisionIntelligenceModel).where(
            PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id,
            PortfolioDecisionIntelligenceModel.risk_snapshot_id == risk_snapshot_id,
            PortfolioDecisionIntelligenceModel.opportunity_id.in_(eligible_ids),
        )).all()) if eligible_ids else []
        row_by_opportunity = {str(row.opportunity_id): row for row in rows}
        missing = sorted(eligible_ids - set(row_by_opportunity))
        if not eligible_ids or missing or len(rows) != len(eligible_ids):
            raise DecisionGenerationCoverageError(
                f"Cannot activate portfolio decisions: eligible={len(eligible_ids)}, "
                f"materialized={len(rows)}, missing={len(missing)}"
            )
        selected_ids = {str(item) for item in selected_opportunity_ids}
        if not optimization_proof.get("optimality_proven"):
            raise DecisionGenerationCoverageError(
                "Cannot activate portfolio decisions without an exact optimizer proof"
            )
        if not selected_ids.issubset(eligible_ids):
            raise DecisionGenerationCoverageError(
                "Optimizer selected an opportunity outside current executable authority"
            )

        stamp = utc_now()
        for opportunity_id, row in row_by_opportunity.items():
            payload = dict(row.payload_json or {})
            optimizer_selected = opportunity_id in selected_ids
            payload["optimizer_selection"] = {
                "status": (
                    "SELECTED_GLOBAL_FEASIBLE"
                    if optimizer_selected
                    else "NOT_SELECTED_GLOBAL_FEASIBLE"
                ),
                "selected": optimizer_selected,
                "solver": optimization_proof.get("solver"),
                "optimality_proven": True,
                "objective": optimization_proof.get("objective"),
                "objective_total_score": optimization_proof.get(
                    "objective_total_score"
                ),
                "max_new_positions": optimization_proof.get(
                    "max_new_positions"
                ),
                "max_new_positions_source": optimization_proof.get(
                    "max_new_positions_source"
                ),
            }
            lifecycle = dict(payload.get("lifecycle") or {})
            lifecycle.update({
                "status": "CURRENT",
                "authority": "CURRENT_PORTFOLIO_ALLOCATION_PUBLICATION",
                "activated_at": stamp,
                "source_stock_scanner_run_id": stock_scanner_run_id,
                "risk_snapshot_id": risk_snapshot_id,
                "state_hash_algorithm": "PYTHON_SORTED_JSON_SHA256_V1",
            })
            payload["lifecycle"] = lifecycle
            row.payload_json = payload
            row.state_hash = sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
            decision_snapshot = session.scalar(select(InstitutionalDecisionSnapshotModel).where(
                InstitutionalDecisionSnapshotModel.opportunity_id == opportunity_id
            ))
            if decision_snapshot is None:
                raise DecisionGenerationCoverageError(
                    f"Institutional decision snapshot disappeared for {opportunity_id}"
                )
            embedded = dict(decision_snapshot.payload_json or {})
            embedded["portfolio_decision"] = payload
            decision_snapshot.payload_json = embedded

        retirement_execution_mode = (
            "POSTGRESQL_SERVER_SIDE_JSONB"
            if session.bind is not None and session.bind.dialect.name == "postgresql"
            else "BOUNDED_CLIENT_COMPATIBILITY"
        )
        if progress:
            progress("stale_decision_retirement_started", {
                "portfolio_id": portfolio_id,
                "risk_snapshot_id": risk_snapshot_id,
                "batch_size": self.STALE_RETIREMENT_BATCH_SIZE,
                "execution_mode": retirement_execution_mode,
            })
        retired = self._retire_stale_decisions(
            session,
            portfolio_id=portfolio_id,
            current_risk_snapshot_id=risk_snapshot_id,
            current_stock_run_id=stock_scanner_run_id,
            progress=progress,
        )
        if progress:
            progress("stale_decision_retirement_completed", {
                "portfolio_id": portfolio_id,
                "risk_snapshot_id": risk_snapshot_id,
                "superseded": retired,
            })
        session.flush()
        return {
            "status": "CURRENT",
            "eligible": len(eligible_ids),
            "activated": len(rows),
            "missing": 0,
            "superseded": retired,
            "retirement_execution_mode": retirement_execution_mode,
            "stock_scanner_run_id": stock_scanner_run_id,
            "risk_snapshot_id": risk_snapshot_id,
        }

    def _retire_stale_decisions(
        self,
        session,
        portfolio_id: str,
        current_risk_snapshot_id: str,
        current_stock_run_id: str | None,
        *,
        progress=None,
    ) -> int:
        """Atomically supersede historical decisions without client JSON I/O.

        PostgreSQL uses a writable CTE to select, mutate, SHA-256 hash, and
        update a bounded set of rows in one server-side statement.  Historical
        explainability documents never cross the client connection.  SQLite and
        other test dialects retain a bounded compatibility implementation.

        The caller owns the surrounding publication transaction.  No retirement
        batch is visible unless the complete current authority also commits.
        """
        dialect_name = (
            session.bind.dialect.name
            if session.bind is not None
            else "unknown"
        )
        if dialect_name == "postgresql":
            return self._retire_stale_decisions_postgresql(
                session,
                portfolio_id=portfolio_id,
                current_risk_snapshot_id=current_risk_snapshot_id,
                current_stock_run_id=current_stock_run_id,
                progress=progress,
            )
        return self._retire_stale_decisions_compatibility(
            session,
            portfolio_id=portfolio_id,
            current_risk_snapshot_id=current_risk_snapshot_id,
            current_stock_run_id=current_stock_run_id,
            progress=progress,
        )

    def _retire_stale_decisions_postgresql(
        self,
        session,
        *,
        portfolio_id: str,
        current_risk_snapshot_id: str,
        current_stock_run_id: str | None,
        progress=None,
    ) -> int:
        """Use PostgreSQL JSONB and core SHA-256 functions server-side."""
        session.execute(text(
            f"SET LOCAL lock_timeout = '{self.STALE_RETIREMENT_LOCK_TIMEOUT_MS}ms'"
        ))
        statement = text("""
            WITH candidates AS (
                SELECT
                    decision_intelligence_id,
                    (
                        COALESCE(payload_json::jsonb, '{}'::jsonb)
                        || jsonb_build_object(
                            'lifecycle',
                            COALESCE(payload_json::jsonb -> 'lifecycle', '{}'::jsonb)
                            || jsonb_build_object(
                                'status', 'SUPERSEDED',
                                'superseded_at', CAST(:superseded_at AS text),
                                'superseded_by_risk_snapshot_id', CAST(:current_risk_snapshot_id AS text),
                                'superseded_by_stock_scanner_run_id', CAST(:current_stock_run_id AS text),
                                'state_hash_algorithm', 'POSTGRESQL_JSONB_CANONICAL_SHA256_V1'
                            )
                        )
                    ) AS next_payload
                FROM portfolio_decision_intelligence_snapshots
                WHERE portfolio_id = :portfolio_id
                  AND risk_snapshot_id <> :current_risk_snapshot_id
                  AND COALESCE(payload_json::jsonb #>> '{lifecycle,status}', '') <> 'SUPERSEDED'
                ORDER BY decision_intelligence_id
                LIMIT :batch_size
                FOR UPDATE
            ), updated AS (
                UPDATE portfolio_decision_intelligence_snapshots AS target
                SET
                    payload_json = CAST(candidates.next_payload AS json),
                    state_hash = encode(
                        sha256(convert_to(candidates.next_payload::text, 'UTF8')),
                        'hex'
                    )
                FROM candidates
                WHERE target.decision_intelligence_id = candidates.decision_intelligence_id
                RETURNING target.decision_intelligence_id
            )
            SELECT
                COUNT(*) AS updated_count,
                MIN(decision_intelligence_id) AS first_decision_id,
                MAX(decision_intelligence_id) AS last_decision_id
            FROM updated
        """)
        retired = 0
        batch_number = 0
        stamp = utc_now()
        started = time.monotonic()
        while True:
            elapsed = time.monotonic() - started
            remaining_ms = int(
                (self.STALE_RETIREMENT_TOTAL_TIMEOUT_SECONDS - elapsed) * 1000
            )
            if remaining_ms <= 0:
                raise RuntimeError(
                    "M64 stale-decision retirement exceeded the governed "
                    f"{self.STALE_RETIREMENT_TOTAL_TIMEOUT_SECONDS:.0f}s total timeout"
                )
            statement_timeout_ms = min(
                self.STALE_RETIREMENT_STATEMENT_TIMEOUT_MS,
                max(1, remaining_ms),
            )
            session.execute(text(
                f"SET LOCAL statement_timeout = '{statement_timeout_ms}ms'"
            ))
            result = session.execute(statement, {
                "portfolio_id": portfolio_id,
                "current_risk_snapshot_id": current_risk_snapshot_id,
                "current_stock_run_id": current_stock_run_id,
                "superseded_at": stamp,
                "batch_size": self.STALE_RETIREMENT_BATCH_SIZE,
            }).one()
            batch_rows = int(result.updated_count or 0)
            if batch_rows == 0:
                break
            batch_number += 1
            retired += batch_rows
            elapsed = time.monotonic() - started
            if progress:
                progress("stale_decision_retirement_batch", {
                    "batch": batch_number,
                    "batch_rows": batch_rows,
                    "superseded": retired,
                    "first_decision_id": result.first_decision_id,
                    "last_decision_id": result.last_decision_id,
                    "execution_mode": "POSTGRESQL_SERVER_SIDE_JSONB",
                    "state_hash_algorithm": "POSTGRESQL_JSONB_CANONICAL_SHA256_V1",
                    "elapsed_seconds": round(elapsed, 3),
                })
            if elapsed > self.STALE_RETIREMENT_TOTAL_TIMEOUT_SECONDS:
                raise RuntimeError(
                    "M64 stale-decision retirement exceeded the governed "
                    f"{self.STALE_RETIREMENT_TOTAL_TIMEOUT_SECONDS:.0f}s total timeout"
                )
        elapsed = time.monotonic() - started
        remaining_ms = int(
            (self.STALE_RETIREMENT_TOTAL_TIMEOUT_SECONDS - elapsed) * 1000
        )
        if remaining_ms <= 0:
            raise RuntimeError(
                "M64 stale-decision retirement exceeded the governed "
                f"{self.STALE_RETIREMENT_TOTAL_TIMEOUT_SECONDS:.0f}s total timeout"
            )
        session.execute(text(
            f"SET LOCAL statement_timeout = '{min(self.STALE_RETIREMENT_STATEMENT_TIMEOUT_MS, max(1, remaining_ms))}ms'"
        ))
        remaining = int(session.scalar(text("""
            SELECT COUNT(*)
            FROM portfolio_decision_intelligence_snapshots
            WHERE portfolio_id = :portfolio_id
              AND risk_snapshot_id <> :current_risk_snapshot_id
              AND COALESCE(payload_json::jsonb #>> '{lifecycle,status}', '') <> 'SUPERSEDED'
        """), {
            "portfolio_id": portfolio_id,
            "current_risk_snapshot_id": current_risk_snapshot_id,
        }) or 0)
        if remaining:
            raise RuntimeError(
                f"M64 stale-decision retirement validation found {remaining} remaining rows"
            )
        if progress:
            progress("stale_decision_retirement_validated", {
                "superseded": retired,
                "remaining": remaining,
                "execution_mode": "POSTGRESQL_SERVER_SIDE_JSONB",
                "elapsed_seconds": round(time.monotonic() - started, 3),
            })
        return retired

    def _retire_stale_decisions_compatibility(
        self,
        session,
        *,
        portfolio_id: str,
        current_risk_snapshot_id: str,
        current_stock_run_id: str | None,
        progress=None,
    ) -> int:
        """Bounded non-PostgreSQL implementation used by portable tests."""
        model = PortfolioDecisionIntelligenceModel
        table = model.__table__
        lifecycle_status = model.payload_json["lifecycle"]["status"].as_string()
        cursor: str | None = None
        retired = 0
        scanned = 0
        batch_number = 0
        stamp = utc_now()
        started = time.monotonic()

        update_statement = (
            table.update()
            .where(table.c.decision_intelligence_id == bindparam("_decision_id"))
            .values(
                payload_json=bindparam("_payload_json"),
                state_hash=bindparam("_state_hash"),
            )
        )

        while True:
            predicates = [
                model.portfolio_id == portfolio_id,
                model.risk_snapshot_id != current_risk_snapshot_id,
                or_(lifecycle_status.is_(None), lifecycle_status != "SUPERSEDED"),
            ]
            if cursor is not None:
                predicates.append(model.decision_intelligence_id > cursor)
            rows = list(session.execute(
                select(model.decision_intelligence_id, model.payload_json)
                .where(*predicates)
                .order_by(model.decision_intelligence_id)
                .limit(self.STALE_RETIREMENT_BATCH_SIZE)
            ).all())
            if not rows:
                break

            batch_number += 1
            scanned += len(rows)
            cursor = str(rows[-1].decision_intelligence_id)
            updates = []
            for decision_id, source_payload in rows:
                payload = dict(source_payload or {})
                lifecycle = dict(payload.get("lifecycle") or {})
                lifecycle.update({
                    "status": "SUPERSEDED",
                    "superseded_at": stamp,
                    "superseded_by_risk_snapshot_id": current_risk_snapshot_id,
                    "superseded_by_stock_scanner_run_id": current_stock_run_id,
                    "state_hash_algorithm": "PYTHON_SORTED_JSON_SHA256_V1",
                })
                payload["lifecycle"] = lifecycle
                updates.append({
                    "_decision_id": str(decision_id),
                    "_payload_json": payload,
                    "_state_hash": sha256(
                        json.dumps(payload, sort_keys=True, default=str).encode()
                    ).hexdigest(),
                })

            if updates:
                session.execute(update_statement, updates)
                session.flush()
                retired += len(updates)
            if progress:
                progress("stale_decision_retirement_batch", {
                    "batch": batch_number,
                    "batch_rows": len(rows),
                    "scanned": scanned,
                    "superseded": retired,
                    "cursor": cursor,
                    "execution_mode": "BOUNDED_CLIENT_COMPATIBILITY",
                    "state_hash_algorithm": "PYTHON_SORTED_JSON_SHA256_V1",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                })
            if time.monotonic() - started > self.STALE_RETIREMENT_TOTAL_TIMEOUT_SECONDS:
                raise RuntimeError(
                    "M64 compatibility retirement exceeded the governed "
                    f"{self.STALE_RETIREMENT_TOTAL_TIMEOUT_SECONDS:.0f}s total timeout"
                )

        return retired

    @staticmethod
    def _authoritative_risk_snapshot_id(session, portfolio_id: str) -> str | None:
        publication = session.scalar(select(PortfolioIntelligencePublicationModel).where(
            PortfolioIntelligencePublicationModel.portfolio_id == portfolio_id,
            PortfolioIntelligencePublicationModel.publication_name == "current_portfolio_allocation",
        ))
        return None if publication is None else str(publication.risk_snapshot_id)

    def current(self, opportunity_id: str, portfolio_id: str = "PAPER-PRIMARY"):
        with self.session_factory() as session:
            authoritative_risk_id = self._authoritative_risk_snapshot_id(session, portfolio_id)
            if authoritative_risk_id is None:
                return None
            row = session.scalar(select(PortfolioDecisionIntelligenceModel).where(
                PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id,
                PortfolioDecisionIntelligenceModel.opportunity_id == opportunity_id,
                PortfolioDecisionIntelligenceModel.risk_snapshot_id == authoritative_risk_id,
            ).limit(1))
            payload = {} if row is None else dict(row.payload_json or {})
            return payload if (payload.get("lifecycle") or {}).get("status") == "CURRENT" else None

    def rankings(self, portfolio_id: str = "PAPER-PRIMARY", limit: int = 100):
        with self.session_factory() as session:
            authoritative_risk_id = self._authoritative_risk_snapshot_id(session, portfolio_id)
            if authoritative_risk_id is None:
                return []
            query = select(PortfolioDecisionIntelligenceModel).where(
                PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id,
                PortfolioDecisionIntelligenceModel.risk_snapshot_id == authoritative_risk_id,
            )
            rows = list(session.scalars(
                query.order_by(PortfolioDecisionIntelligenceModel.rank.asc()).limit(limit)
            ).all())
            payloads = [dict(row.payload_json or {}) for row in rows]
            return [payload for payload in payloads if (payload.get("lifecycle") or {}).get("status") == "CURRENT"]

    def _candidate_greeks(self, selected_contract: dict) -> dict:
        scorecard = selected_contract.get("contract_scorecard") or selected_contract.get("scorecard") or {}
        greeks = selected_contract.get("greeks") or scorecard.get("greeks") or {}
        return {name: number(greeks.get(name)) for name in ("delta","gamma","theta","vega","rho")}

    def _marginal_impact(self, risk: dict, capital: float, greeks: dict, corr: float) -> dict:
        payload=risk["payload_json"]; net=max(number(risk["net_liquidation"]),1)
        before=payload["greeks"]; heat=number(risk["portfolio_heat_pct"]); var=number(risk["var_95"])
        quantity=max(1, int(min(net*.02, max(capital,1))/max(capital,1)))
        marginal={k:number(greeks.get(k))*100*quantity for k in ("delta","gamma","theta","vega","rho")}
        marginal_var=abs(marginal["delta"])*.012 + abs(marginal["gamma"])*.2 + abs(marginal["vega"])*.03
        return {
            "before": {"greeks": before, "var_95": var, "portfolio_heat_pct": heat, "capital_usage_pct": payload["capital"]["capital_usage_pct"]},
            "marginal_greeks": marginal,
            "marginal_var_95": marginal_var,
            "marginal_heat_pct": capital/net*100,
            "after": {"delta":number(before.get("delta"))+marginal["delta"], "gamma":number(before.get("gamma"))+marginal["gamma"], "theta":number(before.get("theta"))+marginal["theta"], "vega":number(before.get("vega"))+marginal["vega"], "var_95":var+marginal_var, "portfolio_heat_pct":heat+capital/net*100},
            "correlation_penalty": abs(corr)*100,
        }

    def _correlation_snapshot(self, session, portfolio_id: str, risk: dict, candidates: list[str]) -> dict:
        symbols=set(candidates)
        symbols.update((risk.get("payload_json") or {}).get("exposures",{}).get("symbol",{}).keys())
        symbols.discard(""); matrix={}; tables=inspect(session.get_bind()).get_table_names()
        if "price_history" in tables:
            table=Table("price_history",MetaData(),autoload_with=session.get_bind())
            series={s:self._returns(session,table,s) for s in symbols}
            for a in symbols:
                matrix[a]={}
                for b in symbols: matrix[a][b]=self._corr(series.get(a,{}),series.get(b,{}))
        payload={"policy_version":self.POLICY_VERSION,"windows":[60],"symbols":sorted(symbols),"matrix":matrix}
        row=PortfolioCorrelationSnapshotModel(correlation_snapshot_id="M64-CORR-"+uuid4().hex.upper(),portfolio_id=portfolio_id,risk_snapshot_id=risk["snapshot_id"],generated_at=utc_now(),payload_json=payload)
        session.add(row); session.flush()
        return {"correlation_snapshot_id":row.correlation_snapshot_id,**payload}

    def _returns(self, session, table, symbol):
        rows=session.execute(select(table.c.date,table.c.close).where(func.upper(table.c.symbol)==symbol.upper()).order_by(table.c.date.desc()).limit(61)).all()
        rows=list(reversed(rows)); out={}
        for i in range(1,len(rows)):
            prev=number(rows[i-1][1]); cur=number(rows[i][1])
            if prev>0: out[str(rows[i][0])]=cur/prev-1
        return out

    def _corr(self,a,b):
        keys=sorted(set(a)&set(b))
        if len(keys)<10:return 0.0
        x=[a[k] for k in keys];y=[b[k] for k in keys];mx=sum(x)/len(x);my=sum(y)/len(y)
        num=sum((u-mx)*(v-my) for u,v in zip(x,y));dx=sqrt(sum((u-mx)**2 for u in x));dy=sqrt(sum((v-my)**2 for v in y))
        return num/(dx*dy) if dx and dy else 0.0

    def _portfolio_correlation(self,symbol,corr):
        row=(corr.get("matrix") or {}).get(symbol,{})
        values=[abs(number(v)) for k,v in row.items() if k!=symbol]
        return sum(values)/len(values) if values else 0.0

    def _decision_evaluation(self, score, fit, marginal):
        """Preserve M64 decision thresholds while making every outcome explainable."""
        fit_decision = str(fit.get("decision") or "").upper()
        input_status = str(fit.get("assessment_status") or (fit.get("input_integrity") or {}).get("status") or "READY").upper()
        projected_heat = number((marginal.get("after") or {}).get("portfolio_heat_pct"))
        blocking_reasons: list[str] = []
        review_reasons: list[str] = []

        if input_status != "READY":
            blocking_reasons.append("PORTFOLIO_INPUT_INTEGRITY_BLOCK")
            blocking_reasons.extend(list(fit.get("blocking_reasons") or []))
        if fit_decision == "REJECT":
            blocking_reasons.append("PORTFOLIO_FIT_REJECT")
        if score < 55:
            blocking_reasons.append("FINAL_PORTFOLIO_SCORE_BELOW_55")
        if not blocking_reasons and score < 72:
            review_reasons.append("FINAL_PORTFOLIO_SCORE_BELOW_72_ACCEPT_THRESHOLD")
        if not blocking_reasons and projected_heat > 20:
            review_reasons.append("PROJECTED_PORTFOLIO_HEAT_ABOVE_20_PCT")

        if blocking_reasons:
            decision = "REJECT"
        elif review_reasons:
            decision = "REVIEW"
        else:
            decision = "ACCEPT"

        return {
            "version": "M76.2.4-PORTFOLIO-DECISION-GOVERNANCE-1.0",
            "decision": decision,
            "input_integrity_status": input_status,
            "fit_decision": fit_decision or "UNKNOWN",
            "fit_score": number(fit.get("portfolio_fit_score")),
            "final_portfolio_score": number(score),
            "projected_portfolio_heat_pct": projected_heat,
            "blocking_reasons": list(dict.fromkeys(blocking_reasons)),
            "review_reasons": list(dict.fromkeys(review_reasons)),
            "thresholds": {
                "reject_final_score_below": 55.0,
                "accept_final_score_min": 72.0,
                "review_heat_above_pct": 20.0,
            },
            "fit_rule_evaluations": list(fit.get("rule_evaluations") or []),
            "fit_input_integrity": dict(fit.get("input_integrity") or {}),
            "fit_policy_thresholds": dict(fit.get("policy_thresholds") or {}),
        }

    def _decision(self, score, fit_decision, marginal):
        # Backward-compatible helper; thresholds remain unchanged.
        fit = {"decision": fit_decision, "assessment_status": "READY"}
        return self._decision_evaluation(score, fit, marginal)["decision"]

    def _explain(self,item,opportunity_cost,decision,rank,decision_governance=None):
        positive=[]; risks=[]
        if item["fit"]["portfolio_fit_score"]>=80:positive.append("Strong portfolio fit")
        if abs(item["correlation"])<.35:positive.append("Low correlation with current portfolio")
        if item["diversification_benefit"]>=65:positive.append("Improves diversification")
        if item["capital_efficiency"]>=50:positive.append("Capital efficient expected value")
        if opportunity_cost>=85:positive.append("Competitive use of available capital")
        for reason in item["fit"].get("reasons",[]):
            if "LIMIT" in reason or "INPUT_" in reason or "UNIT_RISK" in reason:
                risks.append(reason.replace("_"," ").title())
        if item["marginal"]["after"]["portfolio_heat_pct"]>20:risks.append("Portfolio heat would exceed policy")
        governance = dict(decision_governance or {})
        for reason in governance.get("blocking_reasons", []):
            label = str(reason).replace("_", " ").title()
            if label not in risks: risks.append(label)
        for reason in governance.get("review_reasons", []):
            label = str(reason).replace("_", " ").title()
            if label not in risks: risks.append(label)
        return {
            "summary":f"{decision}: portfolio rank {rank}",
            "positive_reasons":positive,
            "risk_reasons":risks,
            "decision_reason_codes":list(governance.get("blocking_reasons", []))+list(governance.get("review_reasons", [])),
            "input_integrity_status":governance.get("input_integrity_status", "UNKNOWN"),
            "why_not_higher_ranked":None if rank==1 else "A higher-ranked candidate offers better expected portfolio improvement.",
        }
