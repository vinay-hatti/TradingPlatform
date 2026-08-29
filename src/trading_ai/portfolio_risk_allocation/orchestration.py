from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import time

from sqlalchemy import MetaData, Table, func, inspect, select, text

from trading_ai.institutional_options.models import (
    ExecutionRecommendationModel,
    InstitutionalDecisionSnapshotModel,
    InstitutionalOpportunityModel,
)
from trading_ai.institutional_options.trade_builder_authority import (
    certified_ready_opportunity_ids,
    classify_trade_builder_authority,
)
from trading_ai.institutional_options.publication_scope import (
    latest_stock_scanner_run_id,
)
from trading_ai.portfolio_management.database_models import (
    PortfolioPositionModel,
)

from .service import PortfolioRiskAllocationService
from .decision_intelligence import InstitutionalDecisionIntelligenceService
from .history_governance import M64DecisionHistoryPurgeService
from .models import (
    PortfolioDecisionIntelligenceModel,
    PortfolioIntelligencePublicationModel,
    PortfolioOptimizationSnapshotModel,
    PortfolioRiskSnapshotModel,
)
from .optimizer import PortfolioOptimizationService
from trading_ai.institutional_options.advancement_authority import (
    validate_current_advancement_authority,
)


class M64CycleBusyError(RuntimeError):
    """Raised when another authoritative M64 cycle owns the portfolio lock."""

    def __init__(self, portfolio_id: str, timeout_seconds: float, owner: dict | None):
        self.portfolio_id = portfolio_id
        self.timeout_seconds = timeout_seconds
        self.owner = dict(owner or {})
        owner_pid = self.owner.get("pid")
        super().__init__(
            f"M64 authoritative cycle is busy for {portfolio_id}; "
            f"lock timeout={timeout_seconds:.3f}s"
            + (f", owner_pid={owner_pid}" if owner_pid is not None else "")
        )

    def as_dict(self) -> dict:
        return {
            "status": "DEFERRED_BUSY",
            "portfolio_id": self.portfolio_id,
            "lock_timeout_seconds": self.timeout_seconds,
            "lock_owner": self.owner,
            "retryable": True,
        }


class M64HistoryCleanupIncompleteError(RuntimeError):
    """Raised after a bounded cleanup pass commits resumable progress."""

    def __init__(self, portfolio_id: str, cleanup: dict):
        self.portfolio_id = portfolio_id
        self.cleanup = dict(cleanup)
        super().__init__(
            f"M64 historical cleanup is incomplete for {portfolio_id}; "
            f"remaining={int(self.cleanup.get('remaining') or 0)}"
        )

    def as_dict(self) -> dict:
        return {
            "status": "DEFERRED_HISTORY_CLEANUP",
            "portfolio_id": self.portfolio_id,
            "historical_cleanup": self.cleanup,
            "retryable": True,
        }


class Milestone64ContinuousPortfolioIntelligenceService:
    """Single operational entry point for the complete Milestone 64 cycle."""
    def __init__(self, session_factory):
        self.session_factory=session_factory

    def _lock_owner(self, session, lock_key: str) -> dict:
        row = session.execute(text("""
            SELECT
                activity.pid,
                activity.application_name,
                activity.state,
                activity.wait_event_type,
                activity.wait_event,
                activity.backend_start,
                activity.xact_start,
                activity.query_start,
                LEFT(activity.query, 240) AS query
            FROM pg_locks AS lock
            JOIN pg_stat_activity AS activity ON activity.pid = lock.pid
            WHERE lock.locktype = 'advisory'
              AND lock.granted
              AND activity.pid <> pg_backend_pid()
              AND activity.query LIKE :query_pattern
            ORDER BY activity.query_start
            LIMIT 1
        """), {"query_pattern": f"%{lock_key}%"}).mappings().first()
        return {} if row is None else {
            key: (value.isoformat() if hasattr(value, "isoformat") else value)
            for key, value in row.items()
        }

    @contextmanager
    def _cycle_lock(
        self,
        portfolio_id: str,
        *,
        timeout_seconds: float,
        progress=None,
        poll_interval_seconds: float = 0.25,
    ):
        """Acquire the authoritative lock with a bounded, observable wait."""
        timeout_seconds = max(0.0, float(timeout_seconds))
        poll_interval_seconds = max(0.05, float(poll_interval_seconds))
        with self.session_factory() as session:
            is_postgresql = session.bind is not None and session.bind.dialect.name == "postgresql"
            lock_key = f"trading_ai:m64_authoritative_cycle:{portfolio_id}"
            acquired = not is_postgresql
            started = time.monotonic()
            owner: dict = {}
            try:
                if is_postgresql:
                    attempt = 0
                    while True:
                        attempt += 1
                        acquired = bool(session.scalar(
                            text("SELECT pg_try_advisory_lock(hashtext(:lock_key))"),
                            {"lock_key": lock_key},
                        ))
                        elapsed = time.monotonic() - started
                        if acquired:
                            # Session advisory locks survive transaction commit.
                            # End the SELECT transaction before the potentially
                            # long portfolio cycle so PostgreSQL does not report
                            # the lock owner as idle in transaction.
                            session.commit()
                            break
                        owner = self._lock_owner(session, lock_key)
                        self._emit(
                            progress,
                            "cycle_lock_waiting",
                            portfolio_id=portfolio_id,
                            attempt=attempt,
                            elapsed_seconds=round(elapsed, 3),
                            timeout_seconds=timeout_seconds,
                            lock_owner=owner,
                        )
                        if elapsed >= timeout_seconds:
                            raise M64CycleBusyError(portfolio_id, timeout_seconds, owner)
                        time.sleep(min(poll_interval_seconds, timeout_seconds - elapsed))
                yield {
                    "lock_key": lock_key,
                    "wait_seconds": round(time.monotonic() - started, 3),
                    "acquired_at": datetime.now(timezone.utc).isoformat(),
                }
            finally:
                if is_postgresql and acquired:
                    session.execute(
                        text("SELECT pg_advisory_unlock(hashtext(:lock_key))"),
                        {"lock_key": lock_key},
                    )
                    session.commit()

    @staticmethod
    def _emit(progress, stage: str, **details) -> None:
        if progress:
            progress(stage, details)

    @staticmethod
    def _validate_reusable_risk(risk: dict | None, portfolio_id: str) -> dict:
        if risk is None:
            raise RuntimeError(
                f"No existing portfolio risk snapshot is available for {portfolio_id}"
            )
        payload = dict(risk.get("payload_json") or {})
        capital = dict(payload.get("capital") or {})
        risk_basis = str(capital.get("trading_risk_basis") or "")
        if str(risk.get("status") or "").upper() != "READY":
            raise RuntimeError(
                f"Latest portfolio risk snapshot {risk.get('snapshot_id')} is not READY"
            )
        if float(risk.get("net_liquidation") or capital.get("net_liquidation") or 0) <= 0:
            raise RuntimeError("Reusable portfolio risk snapshot has no net liquidation")
        if float(risk.get("buying_power") or capital.get("buying_power") or 0) <= 0:
            raise RuntimeError("Reusable portfolio risk snapshot has no buying power")
        if risk_basis != "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS":
            raise RuntimeError(
                "Reusable portfolio risk snapshot does not use the governed M64.2 risk basis"
            )
        return risk

    def _authority_input_contract(self, portfolio_id: str, risk: dict) -> dict:
        """Fingerprint every input capable of changing published M64 authority."""
        baseline_risk = None
        with self.session_factory() as session:
            stock_scanner_run_id = latest_stock_scanner_run_id(session)
            opportunities = []
            execution_by_opportunity = {}
            if stock_scanner_run_id:
                certified_ids = certified_ready_opportunity_ids(
                    session,
                    stock_scanner_run_id=stock_scanner_run_id,
                )
                opportunities = list(session.scalars(
                    select(InstitutionalOpportunityModel)
                    .where(
                        InstitutionalOpportunityModel.stock_scanner_run_id
                        == stock_scanner_run_id,
                        InstitutionalOpportunityModel.state
                        == "READY_FOR_EXECUTION",
                        InstitutionalOpportunityModel.opportunity_id.in_(
                            certified_ids
                        ),
                    )
                    .order_by(InstitutionalOpportunityModel.opportunity_id)
                ).all())
                execution_by_opportunity = {
                    str(row.opportunity_id): row for row in (
                        session.scalars(
                            select(ExecutionRecommendationModel).where(
                                ExecutionRecommendationModel.opportunity_id.in_(
                                    certified_ids
                                )
                            )
                        ).all() if certified_ids else []
                    )
                }
            opportunity_ids = tuple(str(row.opportunity_id) for row in opportunities)
            institutional_rows = list(
                session.scalars(
                    select(InstitutionalDecisionSnapshotModel).where(
                        InstitutionalDecisionSnapshotModel.opportunity_id.in_(
                            opportunity_ids
                        )
                    )
                ).all()
            ) if opportunity_ids else []
            institutional_by_opportunity = {
                str(row.opportunity_id): row for row in institutional_rows
            }
            table_names = set(inspect(session.get_bind()).get_table_names())
            correlation_inputs = []
            correlation_symbols = sorted({
                str(row.symbol or "").upper()
                for row in opportunities
                if str(row.symbol or "")
            } | {
                str(symbol or "").upper()
                for symbol in (
                    (risk.get("payload_json") or {})
                    .get("exposures", {})
                    .get("symbol", {})
                )
                if str(symbol or "")
            })
            if "price_history" in table_names:
                price_history = Table(
                    "price_history",
                    MetaData(),
                    autoload_with=session.get_bind(),
                )
                for symbol in correlation_symbols:
                    rows = session.execute(
                        select(price_history.c.date, price_history.c.close)
                        .where(func.upper(price_history.c.symbol) == symbol)
                        .order_by(price_history.c.date.desc())
                        .limit(61)
                    ).all()
                    correlation_inputs.append({
                        "symbol": symbol,
                        "observations": [
                            [str(row.date), row.close]
                            for row in rows
                        ],
                    })
            optimizer_position_inputs = []
            if PortfolioPositionModel.__tablename__ in table_names:
                optimizer_position_inputs = [
                    {
                        "position_id": str(row.position_id),
                        "symbol": str(row.symbol or "").upper(),
                    }
                    for row in session.execute(
                        select(
                            PortfolioPositionModel.position_id,
                            PortfolioPositionModel.symbol,
                        )
                        .where(
                            PortfolioPositionModel.portfolio_id == portfolio_id,
                            PortfolioPositionModel.status == "OPEN",
                        )
                        .order_by(PortfolioPositionModel.position_id)
                    ).all()
                ]
            current_publication = session.scalar(
                select(PortfolioIntelligencePublicationModel).where(
                    PortfolioIntelligencePublicationModel.portfolio_id
                    == portfolio_id,
                    PortfolioIntelligencePublicationModel.publication_name
                    == PortfolioOptimizationService.PUBLICATION_NAME,
                )
            )
            if current_publication is not None:
                baseline_row = session.get(
                    PortfolioRiskSnapshotModel,
                    current_publication.risk_snapshot_id,
                )
                if baseline_row is not None:
                    baseline_risk = {
                        column.name: getattr(baseline_row, column.name)
                        for column in baseline_row.__table__.columns
                    }

        institutional_inputs = []
        missing = []
        for opportunity in opportunities:
            opportunity_id = str(opportunity.opportunity_id)
            decision = institutional_by_opportunity.get(opportunity_id)
            execution = execution_by_opportunity.get(opportunity_id)
            trade_builder_authority = classify_trade_builder_authority(
                None if execution is None else execution.payload_json,
                None if execution is None
                else execution.ready_for_trade_builder,
            )
            if decision is None:
                missing.append(opportunity_id)
            institutional_inputs.append({
                "opportunity_id": opportunity_id,
                "symbol": str(opportunity.symbol or "").upper(),
                "direction": str(opportunity.direction or ""),
                "category": str(opportunity.category or ""),
                "overall_score": opportunity.overall_score,
                "confidence": opportunity.confidence,
                "opportunity_version": int(opportunity.version or 0),
                "stock_state_hash": str(opportunity.stock_state_hash or ""),
                "option_snapshot_id": str(opportunity.option_snapshot_id or ""),
                "institutional_decision_snapshot_id": (
                    None if decision is None else decision.decision_snapshot_id
                ),
                "institutional_decision_state_hash": (
                    None if decision is None else decision.state_hash
                ),
                "institutional_score": (
                    None if decision is None else decision.institutional_score
                ),
                "calibrated_probability": (
                    None if decision is None else decision.calibrated_probability
                ),
                "trade_builder_authority": trade_builder_authority,
                "expected_value": (
                    None if decision is None else decision.expected_value
                ),
                "capital_required": (
                    None if decision is None else decision.capital_required
                ),
                "selected_strategy": (
                    None if decision is None else decision.selected_strategy
                ),
                "institutional_policy_version": (
                    None if decision is None else decision.policy_version
                ),
                "strategy_candidate_id": (
                    None if decision is None else decision.strategy_candidate_id
                ),
                "contract_recommendation_id": (
                    None if decision is None else decision.contract_recommendation_id
                ),
                "valuation_id": (
                    None if decision is None else decision.valuation_id
                ),
                "execution_recommendation_id": (
                    None if decision is None else decision.execution_recommendation_id
                ),
                "management_snapshot_id": (
                    None if decision is None else decision.management_snapshot_id
                ),
            })

        risk_materiality = (
            PortfolioRiskAllocationService.resolve_material_authority(
                risk,
                baseline_risk,
            )
        )
        if not risk_materiality["candidate_integrity_valid"]:
            raise RuntimeError(
                "Transient M64 risk candidate failed exact integrity validation"
            )
        risk_semantic_fingerprint = str(
            risk_materiality["effective_semantic_fingerprint"]
        )
        institutional_set_fingerprint = sha256(
            json.dumps(
                institutional_inputs,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode()
        ).hexdigest()
        correlation_input_fingerprint = sha256(
            json.dumps(
                {
                    "symbols": correlation_symbols,
                    "price_history_materialized": "price_history" in table_names,
                    "inputs": correlation_inputs,
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode()
        ).hexdigest()
        optimizer_position_fingerprint = sha256(
            json.dumps(
                optimizer_position_inputs,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode()
        ).hexdigest()
        policies = {
            "risk": PortfolioRiskAllocationService.POLICY_VERSION,
            "decision": InstitutionalDecisionIntelligenceService.POLICY_VERSION,
            "optimizer": PortfolioOptimizationService.POLICY_VERSION,
            # Runtime policy is part of authority identity.  In particular,
            # changing M64_MAX_NEW_POSITIONS in the project .env must invalidate
            # a prior no-op fingerprint and force a new exact optimization.
            "optimizer_policy": PortfolioOptimizationService.resolved_policy(),
        }
        governed = {
            "version": "M64.2.4.7-AUTHORITY-INPUT-FINGERPRINT-1.0",
            "portfolio_id": portfolio_id,
            "risk_semantic_fingerprint": risk_semantic_fingerprint,
            "stock_scanner_run_id": stock_scanner_run_id,
            "eligible_decision_count": len(opportunity_ids),
            "institutional_decision_set_fingerprint": (
                institutional_set_fingerprint
            ),
            "correlation_input_fingerprint": correlation_input_fingerprint,
            "optimizer_position_fingerprint": optimizer_position_fingerprint,
            "policies": policies,
        }
        fingerprint = sha256(
            json.dumps(
                governed,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode()
        ).hexdigest()
        return {
            **governed,
            "fingerprint": fingerprint,
            "missing_institutional_decisions": missing,
            "_opportunity_ids": opportunity_ids,
            "_risk_materiality": risk_materiality,
        }

    @staticmethod
    def _publication_authority_input(contract: dict) -> dict:
        return {
            key: value
            for key, value in contract.items()
            if not key.startswith("_")
            and key != "missing_institutional_decisions"
        }

    def _current_authority_validation(
        self,
        portfolio_id: str,
        contract: dict,
    ) -> dict:
        """Fail closed unless current publication coverage is still exact."""
        opportunity_ids = tuple(contract.get("_opportunity_ids") or ())
        with self.session_factory() as session:
            publication = session.scalar(
                select(PortfolioIntelligencePublicationModel).where(
                    PortfolioIntelligencePublicationModel.portfolio_id
                    == portfolio_id,
                    PortfolioIntelligencePublicationModel.publication_name
                    == PortfolioOptimizationService.PUBLICATION_NAME,
                )
            )
            if publication is None:
                return {
                    "status": "INVALID",
                    "checks": {"publication_present": False},
                }
            publication_payload = dict(publication.payload_json or {})
            published_input = dict(publication_payload.get("authority_input") or {})
            risk_row = session.get(
                PortfolioRiskSnapshotModel,
                publication.risk_snapshot_id,
            )
            optimization_row = session.get(
                PortfolioOptimizationSnapshotModel,
                publication.optimization_snapshot_id,
            )
            decisions = list(
                session.scalars(
                    select(PortfolioDecisionIntelligenceModel).where(
                        PortfolioDecisionIntelligenceModel.portfolio_id
                        == portfolio_id,
                        PortfolioDecisionIntelligenceModel.risk_snapshot_id
                        == publication.risk_snapshot_id,
                        PortfolioDecisionIntelligenceModel.opportunity_id.in_(
                            opportunity_ids
                        ),
                    )
                ).all()
            ) if opportunity_ids else []
            institutional_rows = list(
                session.scalars(
                    select(InstitutionalDecisionSnapshotModel).where(
                        InstitutionalDecisionSnapshotModel.opportunity_id.in_(
                            opportunity_ids
                        )
                    )
                ).all()
            ) if opportunity_ids else []

        decision_by_opportunity = {
            str(row.opportunity_id): row for row in decisions
        }
        institutional_by_opportunity = {
            str(row.opportunity_id): row for row in institutional_rows
        }
        current_decisions = 0
        embedded_decisions = 0
        optimizer_governed_decisions = 0
        optimizer_selected_decisions = 0
        for opportunity_id in opportunity_ids:
            decision = decision_by_opportunity.get(opportunity_id)
            if decision is not None:
                payload = dict(decision.payload_json or {})
                lifecycle = dict(payload.get("lifecycle") or {})
                identity = dict(payload.get("decision_identity") or {})
                if (
                    lifecycle.get("status") == "CURRENT"
                    and lifecycle.get("source_stock_scanner_run_id")
                    == contract.get("stock_scanner_run_id")
                    and identity.get("risk_snapshot_id")
                    == publication.risk_snapshot_id
                ):
                    current_decisions += 1
                optimizer_selection = dict(
                    payload.get("optimizer_selection") or {}
                )
                if optimizer_selection.get("optimality_proven") is True:
                    optimizer_governed_decisions += 1
                    if optimizer_selection.get("selected") is True:
                        optimizer_selected_decisions += 1
            institutional = institutional_by_opportunity.get(opportunity_id)
            if institutional is not None:
                embedded = dict(
                    (institutional.payload_json or {}).get("portfolio_decision")
                    or {}
                )
                lifecycle = dict(embedded.get("lifecycle") or {})
                identity = dict(embedded.get("decision_identity") or {})
                if (
                    lifecycle.get("status") == "CURRENT"
                    and lifecycle.get("source_stock_scanner_run_id")
                    == contract.get("stock_scanner_run_id")
                    and identity.get("risk_snapshot_id")
                    == publication.risk_snapshot_id
                ):
                    embedded_decisions += 1

        published_risk_fingerprint = None
        computed_published_risk_fingerprint = None
        published_risk_integrity_fingerprint = None
        computed_published_risk_integrity_fingerprint = None
        if risk_row is not None:
            serialized_risk = {
                column.name: getattr(risk_row, column.name)
                for column in risk_row.__table__.columns
            }
            risk_payload = dict(risk_row.payload_json or {})
            published_risk_fingerprint = risk_payload.get(
                "semantic_fingerprint"
            )
            published_risk_integrity_fingerprint = risk_payload.get(
                "state_integrity_fingerprint"
            )
            computed_published_risk_fingerprint = (
                PortfolioRiskAllocationService.semantic_fingerprint(
                    serialized_risk
                )
            )
            computed_published_risk_integrity_fingerprint = (
                PortfolioRiskAllocationService.state_integrity_fingerprint(
                    serialized_risk
                )
            )
        expected_count = len(opportunity_ids)
        publication_status = str(publication.status or "").upper()
        optimization_proof = dict(
            publication_payload.get("optimization_proof") or {}
        )
        global_authority = dict(
            publication_payload.get("global_candidate_authority") or {}
        )
        published_selected_count = int(
            (publication_payload.get("objective") or {}).get(
                "selected_count"
            )
            or 0
        )
        checks = {
            "publication_present": True,
            "publication_governed": publication_status in {
                "READY",
                "REVIEW",
                "DEGRADED",
            },
            "fingerprint_present": bool(published_input.get("fingerprint")),
            "fingerprint_matches": (
                published_input.get("fingerprint") == contract.get("fingerprint")
            ),
            "stock_run_matches": (
                publication_payload.get("stock_scanner_run_id")
                == contract.get("stock_scanner_run_id")
            ),
            "risk_semantics_match": (
                computed_published_risk_fingerprint
                == contract.get("risk_semantic_fingerprint")
            ),
            "risk_fingerprint_integrity": (
                bool(published_risk_fingerprint)
                and published_risk_fingerprint
                == computed_published_risk_fingerprint
                and bool(published_risk_integrity_fingerprint)
                and published_risk_integrity_fingerprint
                == computed_published_risk_integrity_fingerprint
            ),
            "optimization_snapshot_matches": (
                optimization_row is not None
                and optimization_row.portfolio_id == portfolio_id
                and optimization_row.risk_snapshot_id
                == publication.risk_snapshot_id
                and str(optimization_row.status or "").upper()
                == publication_status
            ),
            "eligible_nonzero": expected_count > 0,
            "institutional_decisions_complete": not contract.get(
                "missing_institutional_decisions"
            ),
            "portfolio_decisions_current": current_decisions == expected_count,
            "embedded_decisions_current": embedded_decisions == expected_count,
            "exact_optimizer_proof_current": (
                optimization_proof.get("optimality_proven") is True
                and optimization_proof.get("solver")
                == "DETERMINISTIC_EXACT_BRANCH_AND_BOUND"
            ),
            "global_candidate_authority_complete": (
                global_authority.get("status") == "PROVEN"
                and global_authority.get(
                    "all_source_candidates_classified"
                ) is True
            ),
            "optimizer_decisions_complete": (
                optimizer_governed_decisions == expected_count
            ),
            "optimizer_selected_count_matches": (
                optimizer_selected_decisions == published_selected_count
            ),
        }
        status = "VALID" if all(checks.values()) else "INVALID"
        return {
            "status": status,
            "checks": checks,
            "publication_id": publication.publication_id,
            "publication_status": publication_status,
            "risk_snapshot_id": publication.risk_snapshot_id,
            "optimization_snapshot_id": publication.optimization_snapshot_id,
            "eligible_decision_count": expected_count,
            "decision_count": current_decisions,
            "embedded_decision_count": embedded_decisions,
            "selected_count": published_selected_count,
            "action_count": len(
                publication_payload.get("recommended_actions") or []
            ),
        }

    def _prune_expired_history(self, history_governance, portfolio_id, progress):
        try:
            return history_governance.prune_expired_history(
                portfolio_id,
                progress=progress,
            )
        except Exception as exc:
            result = {
                "status": "DEFERRED_NON_BLOCKING",
                "pruned": 0,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            self._emit(progress, "historical_retention_deferred", **result)
            return result

    def run(
        self,
        portfolio_id='PAPER-PRIMARY',
        actor='m64-continuous-intelligence',
        *,
        risk_snapshot_id: str | None = None,
        reuse_latest_ready_risk: bool = False,
        skip_unchanged_authority: bool = False,
        lock_timeout_seconds: float = 5.0,
        purge_known_invalid_history: bool = False,
        purge_confirmation_token: str | None = None,
        progress=None,
    ):
        cycle_started = time.monotonic()
        self._emit(
            progress,
            "cycle_lock_requested",
            portfolio_id=portfolio_id,
            lock_timeout_seconds=lock_timeout_seconds,
        )
        with self._cycle_lock(
            portfolio_id,
            timeout_seconds=lock_timeout_seconds,
            progress=progress,
        ) as lock_info:
            self._emit(
                progress,
                "cycle_lock_acquired",
                portfolio_id=portfolio_id,
                **lock_info,
            )
            self._emit(
                progress,
                "institutional_options_authority_validation_started",
                portfolio_id=portfolio_id,
            )
            options_authority = validate_current_advancement_authority(
                self.session_factory
            )
            self._emit(
                progress,
                "institutional_options_authority_ready",
                portfolio_id=portfolio_id,
                stock_scanner_run_id=options_authority[
                    "stock_scanner_run_id"
                ],
                opportunity_count=options_authority["opportunity_count"],
                fingerprint=options_authority["fingerprint"],
            )
            risk_service = PortfolioRiskAllocationService(self.session_factory)
            decision_service = InstitutionalDecisionIntelligenceService(
                self.session_factory
            )
            history_governance = M64DecisionHistoryPurgeService(
                self.session_factory
            )
            optimization_service = PortfolioOptimizationService(
                self.session_factory
            )
            historical_purge = None
            authority_input = None
            authority_validation = None
            unchanged_authority = False
            if risk_snapshot_id is not None:
                risk_mode = "PINNED"
                self._emit(
                    progress,
                    "risk_snapshot_lookup_started",
                    mode=risk_mode,
                    risk_snapshot_id=risk_snapshot_id,
                )
                risk = self._validate_reusable_risk(
                    risk_service.snapshot(portfolio_id, risk_snapshot_id),
                    portfolio_id,
                )
            elif reuse_latest_ready_risk:
                risk_mode = "LATEST_READY_REUSE"
                self._emit(progress, "risk_snapshot_lookup_started", mode=risk_mode)
                risk = self._validate_reusable_risk(
                    risk_service.current(portfolio_id),
                    portfolio_id,
                )
            elif skip_unchanged_authority and not purge_known_invalid_history:
                self._emit(
                    progress,
                    "risk_snapshot_build_started",
                    mode="UNCHANGED_AUTHORITY_PREFLIGHT",
                    persist=False,
                )
                candidate_risk = risk_service.build(
                    portfolio_id,
                    actor,
                    persist=False,
                )
                authority_input = self._authority_input_contract(
                    portfolio_id,
                    candidate_risk,
                )
                authority_validation = self._current_authority_validation(
                    portfolio_id,
                    authority_input,
                )
                unchanged_authority = authority_validation.get("status") == "VALID"
                if unchanged_authority:
                    risk_mode = "UNCHANGED_AUTHORITY_REUSE"
                    risk = risk_service.snapshot(
                        portfolio_id,
                        authority_validation["risk_snapshot_id"],
                    )
                else:
                    risk_mode = "REBUILT"
                    risk = risk_service.persist(candidate_risk)
            else:
                risk_mode = "REBUILT"
                self._emit(progress, "risk_snapshot_build_started", mode=risk_mode)
                risk = risk_service.build(portfolio_id,actor)
            if authority_input is None:
                authority_input = self._authority_input_contract(
                    portfolio_id,
                    risk,
                )
            self._emit(
                progress,
                "authority_input_fingerprint_ready",
                fingerprint=authority_input["fingerprint"],
                risk_semantic_fingerprint=authority_input[
                    "risk_semantic_fingerprint"
                ],
                stock_scanner_run_id=authority_input["stock_scanner_run_id"],
                eligible_decision_count=authority_input[
                    "eligible_decision_count"
                ],
                missing_institutional_decisions=len(
                    authority_input["missing_institutional_decisions"]
                ),
                risk_materiality_status=(
                    authority_input.get("_risk_materiality") or {}
                ).get("status"),
                baseline_risk_snapshot_id=(
                    authority_input.get("_risk_materiality") or {}
                ).get("baseline_snapshot_id"),
                suppressed_submaterial_change_count=(
                    (
                        authority_input.get("_risk_materiality") or {}
                    ).get("evaluation")
                    or {}
                ).get("suppressed_submaterial_change_count", 0),
                material_numeric_change_count=(
                    (
                        authority_input.get("_risk_materiality") or {}
                    ).get("evaluation")
                    or {}
                ).get("material_numeric_change_count", 0),
                structural_change_count=(
                    (
                        authority_input.get("_risk_materiality") or {}
                    ).get("evaluation")
                    or {}
                ).get("structural_change_count", 0),
                validation=(authority_validation or {}).get("status"),
            )
            self._emit(
                progress,
                "risk_snapshot_ready",
                mode=risk_mode,
                risk_snapshot_id=risk["snapshot_id"],
                status=risk.get("status"),
                portfolio_heat_pct=risk.get("portfolio_heat_pct"),
            )
            if purge_known_invalid_history:
                if not risk_snapshot_id:
                    raise RuntimeError(
                        "Governed invalid-history purge requires a pinned "
                        "READY risk snapshot"
                    )
                historical_purge = (
                    history_governance.purge_known_invalid_history(
                        portfolio_id,
                        target_risk_snapshot_id=risk_snapshot_id,
                        confirmation_token=str(purge_confirmation_token or ""),
                        progress=progress,
                    )
                )
            history_cleanup = {
                "status": "NOT_BLOCKING_AUTHORITY",
                "complete": True,
                "policy": (
                    "GOVERNED_PURGE_AND_BOUNDED_ASYNC_RETENTION"
                    if historical_purge
                    else "BOUNDED_ASYNC_RETENTION"
                ),
                "purged_rows": int(
                    (historical_purge or {}).get("purged_rows") or 0
                ),
            }
            self._emit(
                progress,
                "historical_governance_ready",
                **history_cleanup,
            )
            if unchanged_authority:
                history_retention = self._prune_expired_history(
                    history_governance,
                    portfolio_id,
                    progress,
                )
                self._emit(
                    progress,
                    "cycle_noop_unchanged_authority",
                    fingerprint=authority_input["fingerprint"],
                    risk_snapshot_id=authority_validation["risk_snapshot_id"],
                    optimization_snapshot_id=authority_validation[
                        "optimization_snapshot_id"
                    ],
                    publication_id=authority_validation["publication_id"],
                    stock_scanner_run_id=authority_input[
                        "stock_scanner_run_id"
                    ],
                    eligible_decision_count=authority_validation[
                        "eligible_decision_count"
                    ],
                    selected_count=authority_validation["selected_count"],
                    checks=authority_validation["checks"],
                )
                return {
                    "version": "M64.2.4.9-GLOBAL-FEASIBLE-CYCLE-1.0",
                    "portfolio_id": portfolio_id,
                    "stock_scanner_run_id": authority_input[
                        "stock_scanner_run_id"
                    ],
                    "risk_snapshot_id": authority_validation[
                        "risk_snapshot_id"
                    ],
                    "eligible_decision_count": authority_validation[
                        "eligible_decision_count"
                    ],
                    "decision_count": authority_validation["decision_count"],
                    "decision_coverage_pct": 100.0,
                    "missing_decision_count": 0,
                    "superseded_decision_count": 0,
                    "optimization_snapshot_id": authority_validation[
                        "optimization_snapshot_id"
                    ],
                    "publication_id": authority_validation["publication_id"],
                    "selected_count": authority_validation["selected_count"],
                    "action_count": authority_validation["action_count"],
                    "risk_snapshot_mode": risk_mode,
                    "authority_input_fingerprint": authority_input[
                        "fingerprint"
                    ],
                    "authoritative_rebuild_performed": False,
                    "cycle_outcome": "NO_CHANGE",
                    "no_op_validation": authority_validation,
                    "historical_cleanup": history_cleanup,
                    "historical_purge": historical_purge,
                    "historical_retention": history_retention,
                    "lock_wait_seconds": lock_info["wait_seconds"],
                    "elapsed_seconds": round(
                        time.monotonic() - cycle_started,
                        3,
                    ),
                    "status": authority_validation["publication_status"],
                }
            self._emit(
                progress,
                "decision_generation_started",
                risk_snapshot_id=risk["snapshot_id"],
            )
            decisions=decision_service.build(
                portfolio_id,
                risk_snapshot_id=risk['snapshot_id'],
                require_complete=True,
                progress=progress,
            )
            self._emit(
                progress,
                "decision_generation_completed",
                risk_snapshot_id=risk["snapshot_id"],
                stock_scanner_run_id=decisions["stock_scanner_run_id"],
                eligible=decisions["eligible"],
                built=decisions["built"],
                missing=len(decisions["missing"]),
                authority_status=decisions["authority_status"],
            )
            self._emit(
                progress,
                "optimizer_publication_started",
                risk_snapshot_id=risk["snapshot_id"],
                stock_scanner_run_id=decisions["stock_scanner_run_id"],
            )
            optimization=optimization_service.build(
                portfolio_id,
                rebuild_decisions=False,
                actor=actor,
                risk_snapshot_id=risk['snapshot_id'],
                stock_scanner_run_id=decisions['stock_scanner_run_id'],
                authority_input=self._publication_authority_input(
                    authority_input
                ),
                progress=progress,
            )
            activation=dict(optimization.get('decision_activation') or {})
            if (
                activation.get('status') != 'CURRENT'
                or int(activation.get('missing') or 0) != 0
                or int(activation.get('activated') or 0) != int(decisions.get('eligible') or 0)
            ):
                raise RuntimeError(
                    'M64 authoritative publication failed decision coverage validation'
                )
            history_retention = self._prune_expired_history(
                history_governance,
                portfolio_id,
                progress,
            )
            return {
                'version':'M64.2.4.9-GLOBAL-FEASIBLE-CYCLE-1.0',
                'portfolio_id':portfolio_id,
                'stock_scanner_run_id':decisions['stock_scanner_run_id'],
                'institutional_options_authority':options_authority,
                'risk_snapshot_id':risk['snapshot_id'],
                'eligible_decision_count':decisions['eligible'],
                'decision_count':decisions['built'],
                'decision_coverage_pct':decisions['coverage_pct'],
                'missing_decision_count':len(decisions['missing']),
                'superseded_decision_count':activation.get('superseded',0),
                'optimization_snapshot_id':optimization['optimization_snapshot_id'],
                'publication_id':optimization['publication_id'],
                'selected_count':len(optimization['selected_candidates']),
                'action_count':len(optimization['recommended_actions']),
                'risk_snapshot_mode':risk_mode,
                'authority_input_fingerprint':authority_input['fingerprint'],
                'authoritative_rebuild_performed':True,
                'cycle_outcome':'AUTHORITY_REBUILT',
                'historical_cleanup':history_cleanup,
                'historical_purge':historical_purge,
                'historical_retention':history_retention,
                'lock_wait_seconds':lock_info['wait_seconds'],
                'elapsed_seconds':round(time.monotonic()-cycle_started,3),
                'status':'READY',
            }
