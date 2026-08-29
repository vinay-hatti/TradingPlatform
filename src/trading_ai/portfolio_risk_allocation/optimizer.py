from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import select, text

from trading_ai.institutional_options.models import (
    ContractRecommendationModel,
    ExecutionRecommendationModel,
    InstitutionalOpportunityModel,
    StrategyCandidateModel,
    StrategyComparisonModel,
)
from trading_ai.institutional_options.opportunity_ingestion import (
    StockOpportunityEligibilityService,
)
from trading_ai.institutional_options.trade_builder_authority import (
    certified_ready_opportunity_ids,
    classify_trade_builder_authority,
)
from trading_ai.institutional_options.publication_scope import latest_stock_scanner_run_id
from trading_ai.portfolio_management.database_models import PortfolioPositionModel

from .decision_intelligence import (
    DecisionGenerationCoverageError,
    InstitutionalDecisionIntelligenceService,
)
from .config import (
    MAX_NEW_POSITIONS_MAX,
    MAX_NEW_POSITIONS_MIN,
    load_portfolio_optimizer_config,
)
from .models import (
    PortfolioDecisionIntelligenceModel,
    PortfolioIntelligencePublicationModel,
    PortfolioOptimizationSnapshotModel,
    PortfolioRecommendationModel,
    PortfolioRiskBudgetSnapshotModel,
    PortfolioRiskSnapshotModel,
)
from .service import PortfolioRiskAllocationService, clamp, number


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PortfolioOptimizationService:
    """Governed exact portfolio optimizer and recommendation publisher.

    Every current Stock Intelligence candidate is classified through the hard
    gates.  The executable-now set is then solved with deterministic exact
    branch-and-bound.  Authority is published only with a complete universe
    ledger and a proof that the selected subset maximizes the governed objective
    under all capital, heat, concentration, and correlation constraints.
    """

    POLICY_VERSION = "M64.2.4.9-GLOBAL-FEASIBLE-OPTIMIZER-1.0"
    PUBLICATION_NAME = "current_portfolio_allocation"

    DEFAULT_POLICY = {
        "max_new_capital_pct": 5.0,
        "max_single_candidate_capital_pct": 2.0,
        "max_portfolio_heat_pct": 20.0,
        "max_symbol_pct": 10.0,
        "max_sector_pct": 25.0,
        "max_strategy_pct": 35.0,
        "max_pair_correlation": 0.80,
        "min_final_portfolio_score": 62.0,
        "max_candidates_considered": 1000,
        "exact_solver_node_limit": 2_000_000,
        "delta_hedge_threshold_pct": 15.0,
        "vega_hedge_threshold_pct": 0.75,
    }

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.risk_service = PortfolioRiskAllocationService(session_factory)
        self.decision_service = InstitutionalDecisionIntelligenceService(session_factory)

    @classmethod
    def resolved_policy(cls, policy: dict | None = None) -> dict:
        """Resolve policy with the position cap owned by the project ``.env``.

        An explicit cap is accepted only for deterministic tests or controlled
        offline simulations.  Normal M64 authority calls provide no override and
        therefore fail closed unless ``M64_MAX_NEW_POSITIONS`` exists in ``.env``.
        """

        supplied = dict(policy or {})
        if "max_new_positions" in supplied:
            max_new_positions = int(supplied["max_new_positions"])
            config_source = "EXPLICIT_CONTROLLED_OVERRIDE"
        else:
            runtime = load_portfolio_optimizer_config()
            max_new_positions = runtime.max_new_positions
            config_source = runtime.source
        if not (
            MAX_NEW_POSITIONS_MIN
            <= max_new_positions
            <= MAX_NEW_POSITIONS_MAX
        ):
            raise ValueError(
                "max_new_positions must be between "
                f"{MAX_NEW_POSITIONS_MIN} and {MAX_NEW_POSITIONS_MAX}"
            )
        return {
            **cls.DEFAULT_POLICY,
            **supplied,
            "max_new_positions": max_new_positions,
            "max_new_positions_source": config_source,
        }

    def build(
        self,
        portfolio_id: str = "PAPER-PRIMARY",
        *,
        rebuild_decisions: bool = True,
        actor: str = "m64-portfolio-optimizer",
        policy: dict | None = None,
        risk_snapshot_id: str | None = None,
        stock_scanner_run_id: str | None = None,
        authority_input: dict | None = None,
        progress=None,
    ) -> dict:
        policy_values = self.resolved_policy(policy)
        risk = self.risk_service.snapshot(portfolio_id, risk_snapshot_id)
        if risk is None and risk_snapshot_id is not None:
            raise LookupError(
                f"Pinned portfolio risk snapshot {risk_snapshot_id} was not found "
                f"for portfolio {portfolio_id}"
            )
        risk = risk or self.risk_service.build(portfolio_id, actor)
        if rebuild_decisions:
            decision_generation = self.decision_service.build(
                portfolio_id,
                risk_snapshot_id=risk["snapshot_id"],
                require_complete=True,
                progress=progress,
            )
            stock_scanner_run_id = decision_generation["stock_scanner_run_id"]

        with self.session_factory() as session:
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                acquired = bool(session.scalar(text(
                    "SELECT pg_try_advisory_xact_lock(hashtext(:lock_key))"
                ), {
                    "lock_key": f"trading_ai:m64_authoritative_publish:{portfolio_id}"
                }))
                if not acquired:
                    raise DecisionGenerationCoverageError(
                        f"M64 authoritative publication is already active for {portfolio_id}"
                    )
            current_publication = session.scalar(select(PortfolioIntelligencePublicationModel).where(
                PortfolioIntelligencePublicationModel.portfolio_id == portfolio_id,
                PortfolioIntelligencePublicationModel.publication_name == self.PUBLICATION_NAME,
            ))
            if current_publication and current_publication.risk_snapshot_id != risk["snapshot_id"]:
                published_risk = session.scalar(select(PortfolioRiskSnapshotModel).where(
                    PortfolioRiskSnapshotModel.snapshot_id == current_publication.risk_snapshot_id,
                    PortfolioRiskSnapshotModel.portfolio_id == portfolio_id,
                ))
                candidate_risk = session.scalar(select(PortfolioRiskSnapshotModel).where(
                    PortfolioRiskSnapshotModel.snapshot_id == risk["snapshot_id"],
                    PortfolioRiskSnapshotModel.portfolio_id == portfolio_id,
                ))
                if (
                    published_risk is not None
                    and candidate_risk is not None
                    and str(published_risk.snapshot_timestamp) > str(candidate_risk.snapshot_timestamp)
                ):
                    raise DecisionGenerationCoverageError(
                        "Refused to replace a newer authoritative portfolio publication "
                        f"({published_risk.snapshot_id}) with older risk snapshot {candidate_risk.snapshot_id}"
                    )
            observed_stock_run_id = latest_stock_scanner_run_id(session)
            governed_stock_run_id = stock_scanner_run_id or observed_stock_run_id
            if not governed_stock_run_id:
                raise DecisionGenerationCoverageError(
                    "No materialized current Stock Intelligence run is available for optimization"
                )
            if observed_stock_run_id != governed_stock_run_id:
                raise DecisionGenerationCoverageError(
                    "Stock Intelligence advanced before portfolio publication: "
                    f"expected {governed_stock_run_id}, observed {observed_stock_run_id}"
                )
            eligible_ids = certified_ready_opportunity_ids(
                session,
                stock_scanner_run_id=governed_stock_run_id,
            )
            decisions = list(
                session.scalars(
                    select(PortfolioDecisionIntelligenceModel)
                    .where(
                        PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id,
                        PortfolioDecisionIntelligenceModel.risk_snapshot_id == risk["snapshot_id"],
                        PortfolioDecisionIntelligenceModel.opportunity_id.in_(eligible_ids),
                    )
                    .order_by(
                        PortfolioDecisionIntelligenceModel.final_portfolio_score.desc(),
                        PortfolioDecisionIntelligenceModel.rank.asc(),
                    )
                ).all()
            ) if eligible_ids else []
            decision_ids = {str(row.opportunity_id) for row in decisions}
            missing_decisions = sorted(eligible_ids - decision_ids)
            if not eligible_ids or missing_decisions or len(decisions) != len(eligible_ids):
                raise DecisionGenerationCoverageError(
                    f"Portfolio optimizer refused incomplete decision authority: "
                    f"eligible={len(eligible_ids)}, decisions={len(decisions)}, "
                    f"missing={len(missing_decisions)}"
                )
            risk_payload = dict(risk.get("payload_json") or {})
            budgets = self._risk_budgets(risk, policy_values)
            selected, rejected, optimization_proof = self._select_candidates(
                decisions, risk, budgets, policy_values
            )
            universe_authority = self._global_universe_authority(
                session,
                governed_stock_run_id,
                decisions,
                selected,
                optimization_proof,
            )
            if not universe_authority["all_source_candidates_classified"]:
                raise DecisionGenerationCoverageError(
                    "Global feasible optimizer refused incomplete Stock "
                    "Intelligence universe classification"
                )
            if progress:
                progress("optimizer_selection_completed", {
                    "eligible": len(eligible_ids),
                    "decisions": len(decisions),
                    "selected": len(selected),
                    "rejected": len(rejected),
                    "optimality_proven": optimization_proof[
                        "optimality_proven"
                    ],
                    "source_universe_count": universe_authority[
                        "source_universe_count"
                    ],
                })
            hedge_recommendations = self._hedge_recommendations(risk, policy_values)
            rebalance_recommendations = self._rebalance_recommendations(
                session, portfolio_id, risk, selected, policy_values
            )
            target = self._target_portfolio(risk, selected)
            objective = self._objective(selected)
            status = self._status(
                selected, decisions, budgets, optimization_proof
            )
            payload = {
                "policy_version": self.POLICY_VERSION,
                "resolved_optimizer_policy": policy_values,
                "generated_by": actor,
                "portfolio_id": portfolio_id,
                "risk_snapshot_id": risk["snapshot_id"],
                "stock_scanner_run_id": governed_stock_run_id,
                "generated_at": utc_now(),
                "status": status,
                "authority_input": dict(authority_input or {}),
                "decision_authority": {
                    "status": "CURRENT",
                    "eligible_candidates": len(eligible_ids),
                    "materialized_decisions": len(decisions),
                    "missing_decisions": 0,
                    "risk_snapshot_id": risk["snapshot_id"],
                    "stock_scanner_run_id": governed_stock_run_id,
                },
                "objective": {
                    "name": "MAXIMIZE_TOTAL_FINAL_PORTFOLIO_SCORE",
                    "score": objective,
                    "total_score": optimization_proof[
                        "objective_total_score"
                    ],
                    "candidate_count": len(decisions),
                    "selected_count": len(selected),
                    "rejected_count": len(rejected),
                },
                "risk_budgets": budgets,
                "current_portfolio": {
                    "net_liquidation": number(risk.get("net_liquidation")),
                    "buying_power": number(risk.get("buying_power")),
                    "capital_committed": number(risk.get("capital_committed")),
                    "portfolio_heat_pct": number(risk.get("portfolio_heat_pct")),
                    "var_95": number(risk.get("var_95")),
                    "expected_shortfall_95": number(risk.get("expected_shortfall_95")),
                    "greeks": risk_payload.get("greeks", {}),
                    "exposures": risk_payload.get("exposures", {}),
                },
                "target_portfolio": target,
                "selected_candidates": selected,
                "rejected_candidates": rejected,
                "best_next_trades": selected,
                "optimization_proof": optimization_proof,
                "global_candidate_authority": universe_authority,
                "hedge_recommendations": hedge_recommendations,
                "rebalance_recommendations": rebalance_recommendations,
                "recommended_actions": [*rebalance_recommendations, *hedge_recommendations],
                "explainability": self._explain(selected, rejected, budgets),
                "future_extensions": {
                    "learning_confidence": None,
                    "inflection_intelligence": None,
                    "option_valuation_intelligence": None,
                },
            }
            if progress:
                progress("decision_activation_started", {
                    "eligible": len(eligible_ids),
                    "risk_snapshot_id": risk["snapshot_id"],
                    "stock_scanner_run_id": governed_stock_run_id,
                })
            activation = self.decision_service.activate_generation(
                session,
                portfolio_id=portfolio_id,
                risk_snapshot_id=risk["snapshot_id"],
                stock_scanner_run_id=governed_stock_run_id,
                selected_opportunity_ids={
                    str(item["opportunity_id"]) for item in selected
                },
                optimization_proof=optimization_proof,
                progress=progress,
            )
            if progress:
                progress("decision_activation_completed", dict(activation))
            payload["decision_authority"].update({
                "activated_decisions": activation["activated"],
                "superseded_decisions": activation["superseded"],
                "retirement_execution_mode": activation["retirement_execution_mode"],
            })
            state_hash = sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()
            snapshot = self._upsert_snapshot(
                session, portfolio_id, risk["snapshot_id"], payload, state_hash
            )
            budget_row = self._upsert_budget(
                session, portfolio_id, risk["snapshot_id"], budgets
            )
            action_rows = self._upsert_actions(
                session,
                portfolio_id,
                risk["snapshot_id"],
                [*rebalance_recommendations, *hedge_recommendations],
            )
            publication = self._upsert_publication(
                session, portfolio_id, risk["snapshot_id"], snapshot, payload
            )
            if progress:
                progress("authoritative_publication_commit_started", {
                    "publication_id": publication.publication_id,
                    "risk_snapshot_id": risk["snapshot_id"],
                    "stock_scanner_run_id": governed_stock_run_id,
                })
            session.commit()
            if progress:
                progress("authoritative_publication_commit_completed", {
                    "publication_id": publication.publication_id,
                    "risk_snapshot_id": risk["snapshot_id"],
                    "stock_scanner_run_id": governed_stock_run_id,
                })
            return {
                **payload,
                "optimization_snapshot_id": snapshot.optimization_snapshot_id,
                "budget_snapshot_id": budget_row.budget_snapshot_id,
                "publication_id": publication.publication_id,
                "persisted_action_count": len(action_rows),
                "decision_activation": activation,
            }

    def current(self, portfolio_id: str = "PAPER-PRIMARY") -> dict | None:
        with self.session_factory() as session:
            row = session.scalar(
                select(PortfolioOptimizationSnapshotModel)
                .where(PortfolioOptimizationSnapshotModel.portfolio_id == portfolio_id)
                .order_by(PortfolioOptimizationSnapshotModel.generated_at.desc())
                .limit(1)
            )
            if row is None:
                return None
            return {
                **dict(row.payload_json or {}),
                "optimization_snapshot_id": row.optimization_snapshot_id,
                "objective_score": row.objective_score,
                "selected_count": row.selected_count,
                "recommended_capital": row.recommended_capital,
            }

    def publication(self, portfolio_id: str = "PAPER-PRIMARY") -> dict | None:
        with self.session_factory() as session:
            row = session.scalar(
                select(PortfolioIntelligencePublicationModel).where(
                    PortfolioIntelligencePublicationModel.portfolio_id == portfolio_id,
                    PortfolioIntelligencePublicationModel.publication_name == self.PUBLICATION_NAME,
                )
            )
            return None if row is None else {
                "publication_id": row.publication_id,
                "publication_name": row.publication_name,
                "portfolio_id": row.portfolio_id,
                "risk_snapshot_id": row.risk_snapshot_id,
                "optimization_snapshot_id": row.optimization_snapshot_id,
                "published_at": row.published_at,
                "status": row.status,
                "payload_json": dict(row.payload_json or {}),
            }

    def recommendations(self, portfolio_id: str = "PAPER-PRIMARY", status: str | None = None) -> list[dict]:
        with self.session_factory() as session:
            query = select(PortfolioRecommendationModel).where(
                PortfolioRecommendationModel.portfolio_id == portfolio_id
            )
            if status:
                query = query.where(PortfolioRecommendationModel.status == status)
            rows = list(session.scalars(query.order_by(PortfolioRecommendationModel.created_at.desc())).all())
            return [
                {
                    "recommendation_id": row.recommendation_id,
                    "action_type": row.action_type,
                    "symbol": row.symbol,
                    "priority": row.priority,
                    "status": row.status,
                    "payload_json": dict(row.payload_json or {}),
                }
                for row in rows
            ]

    def _select_candidates(self, decisions, risk, budgets, policy):
        """Return the exact maximum-score feasible subset and its proof.

        Candidate capital is fixed before solving; it never depends on iteration
        order.  Branch-and-bound explores both include/exclude branches and uses
        only an admissible score upper bound, so a completed search is an exact
        proof rather than a greedy approximation.
        """

        net = max(number(risk.get("net_liquidation")), 1.0)
        available_capital = number(
            budgets["portfolio"]["new_capital_remaining"]
        )
        current_heat = number(risk.get("portfolio_heat_pct"))
        exposures = (risk.get("payload_json") or {}).get("exposures", {})
        current_symbols = dict(exposures.get("symbol") or {})
        current_sectors = dict(exposures.get("sector") or {})
        current_strategies = dict(exposures.get("strategy") or {})

        prepared = [
            self._candidate_record(row, risk, budgets, policy)
            for row in decisions
        ]
        hard_rejected = [
            item for item in prepared if item["hard_gate_reasons"]
        ]
        feasible = sorted(
            [item for item in prepared if not item["hard_gate_reasons"]],
            key=lambda item: (
                -number(item["final_portfolio_score"]),
                int(item.get("rank") or 1_000_000),
                str(item["opportunity_id"]),
            ),
        )
        if len(feasible) > int(policy["max_candidates_considered"]):
            raise DecisionGenerationCoverageError(
                "Exact optimizer candidate count exceeds governed limit: "
                f"feasible={len(feasible)}, "
                f"limit={int(policy['max_candidates_considered'])}"
            )

        max_positions = min(
            int(policy["max_new_positions"]), len(feasible)
        )
        max_heat_increment = max(
            0.0,
            number(policy["max_portfolio_heat_pct"]) - current_heat,
        )
        node_limit = int(policy.get("exact_solver_node_limit", 2_000_000))
        nodes_evaluated = 0
        nodes_pruned = 0
        node_limit_reached = False
        best_indices: tuple[int, ...] = ()
        best_score = 0.0

        def can_add(
            candidate: dict,
            capital: float,
            heat: float,
            symbols: set[str],
            sectors: dict[str, float],
            strategies: dict[str, float],
        ) -> bool:
            symbol = str(candidate["symbol"])
            sector = str(candidate["sector"])
            strategy = str(candidate["strategy"])
            amount = number(candidate["recommended_capital"])
            if symbol in symbols:
                return False
            if capital + amount > available_capital + 1e-9:
                return False
            if heat + number(candidate["marginal_heat_pct"]) > max_heat_increment + 1e-9:
                return False
            if (
                number(current_symbols.get(symbol)) + amount
            ) / net * 100 > number(policy["max_symbol_pct"]) + 1e-9:
                return False
            if (
                number(current_sectors.get(sector))
                + number(sectors.get(sector))
                + amount
            ) / net * 100 > number(policy["max_sector_pct"]) + 1e-9:
                return False
            if (
                number(current_strategies.get(strategy))
                + number(strategies.get(strategy))
                + amount
            ) / net * 100 > number(policy["max_strategy_pct"]) + 1e-9:
                return False
            return True

        def search(
            index: int,
            chosen: tuple[int, ...],
            score: float,
            capital: float,
            heat: float,
            symbols: set[str],
            sectors: dict[str, float],
            strategies: dict[str, float],
        ) -> None:
            nonlocal nodes_evaluated, nodes_pruned, node_limit_reached
            nonlocal best_indices, best_score
            if node_limit_reached:
                return
            nodes_evaluated += 1
            if nodes_evaluated > node_limit:
                node_limit_reached = True
                return
            if score > best_score + 1e-9:
                best_score = score
                best_indices = chosen
            if index >= len(feasible) or len(chosen) >= max_positions:
                return

            slots = max_positions - len(chosen)
            optimistic = score + sum(
                number(item["final_portfolio_score"])
                for item in feasible[index:index + slots]
            )
            if optimistic <= best_score + 1e-9:
                nodes_pruned += 1
                return

            candidate = feasible[index]
            if can_add(
                candidate, capital, heat, symbols, sectors, strategies
            ):
                symbol = str(candidate["symbol"])
                sector = str(candidate["sector"])
                strategy = str(candidate["strategy"])
                amount = number(candidate["recommended_capital"])
                next_sectors = dict(sectors)
                next_strategies = dict(strategies)
                next_sectors[sector] = number(next_sectors.get(sector)) + amount
                next_strategies[strategy] = (
                    number(next_strategies.get(strategy)) + amount
                )
                search(
                    index + 1,
                    (*chosen, index),
                    score + number(candidate["final_portfolio_score"]),
                    capital + amount,
                    heat + number(candidate["marginal_heat_pct"]),
                    {*symbols, symbol},
                    next_sectors,
                    next_strategies,
                )
            search(
                index + 1,
                chosen,
                score,
                capital,
                heat,
                symbols,
                sectors,
                strategies,
            )

        search(0, (), 0.0, 0.0, 0.0, set(), {}, {})
        optimality_proven = not node_limit_reached
        if not optimality_proven:
            raise DecisionGenerationCoverageError(
                "Exact portfolio optimizer reached its governed node limit "
                f"({node_limit}) before proving global optimality; no new "
                "portfolio authority was published"
            )

        selected_ids = {feasible[index]["opportunity_id"] for index in best_indices}
        selected: list[dict] = []
        rejected: list[dict] = []
        for feasible_rank, candidate in enumerate(feasible, 1):
            item = dict(candidate)
            item.pop("hard_gate_reasons", None)
            item["global_feasible_rank"] = feasible_rank
            if item["opportunity_id"] in selected_ids:
                item["optimizer_decision"] = "SELECT"
                item["selection_reason"] = self._selection_reason(item)
                selected.append(item)
            else:
                reasons = ["NOT_IN_GLOBAL_OPTIMAL_SUBSET"]
                if len(selected_ids) >= max_positions:
                    reasons.append("MAX_NEW_POSITIONS")
                item["optimizer_decision"] = "SKIP"
                item["rejection_reasons"] = reasons
                rejected.append(item)
        for candidate in hard_rejected:
            item = dict(candidate)
            reasons = list(item.pop("hard_gate_reasons"))
            item["optimizer_decision"] = "SKIP"
            item["rejection_reasons"] = reasons
            item["globally_feasible_rank"] = None
            rejected.append(item)

        selected.sort(
            key=lambda item: (
                -number(item["final_portfolio_score"]),
                int(item.get("rank") or 1_000_000),
                str(item["opportunity_id"]),
            )
        )
        rejected.sort(
            key=lambda item: (
                -number(item["final_portfolio_score"]),
                int(item.get("rank") or 1_000_000),
                str(item["opportunity_id"]),
            )
        )
        proof = {
            "version": "M64.2.4.9-EXACT-BRANCH-AND-BOUND-PROOF-1.0",
            "solver": "DETERMINISTIC_EXACT_BRANCH_AND_BOUND",
            "optimality_proven": True,
            "objective": "MAXIMIZE_TOTAL_FINAL_PORTFOLIO_SCORE",
            "objective_total_score": round(best_score, 6),
            "candidate_decisions_evaluated": len(prepared),
            "hard_gate_eligible_candidates": len(feasible),
            "hard_gate_excluded_candidates": len(hard_rejected),
            "selected_count": len(selected),
            "max_new_positions": int(policy["max_new_positions"]),
            "max_new_positions_source": policy[
                "max_new_positions_source"
            ],
            "nodes_evaluated": nodes_evaluated,
            "nodes_pruned_by_admissible_bound": nodes_pruned,
            "node_limit": node_limit,
            "selected_opportunity_ids": [
                item["opportunity_id"] for item in selected
            ],
            "selected_global_feasible_ranks": [
                item["global_feasible_rank"] for item in selected
            ],
            "all_feasible_subsets_covered_by_search_or_bound": True,
            "order_independent_candidate_capital": True,
        }
        return selected, rejected, proof

    def _candidate_record(self, row, risk, budgets, policy) -> dict:
        payload = dict(row.payload_json or {})
        identity = payload.get("decision_identity") or {}
        symbol = self._symbol(payload)
        sector = self._sector(payload)
        strategy = self._strategy(payload)
        allocation = payload.get("capital_allocation") or {}
        impact = payload.get("portfolio_impact") or {}
        scores = payload.get("scores") or {}
        requested_qty = max(
            0, int(number(allocation.get("recommended_quantity")))
        )
        requested_capital = max(
            0.0, number(allocation.get("recommended_capital"))
        )
        unit_capital = requested_capital / max(requested_qty, 1)
        net = max(number(risk.get("net_liquidation")), 1.0)
        max_per_candidate = (
            net * number(policy["max_single_candidate_capital_pct"]) / 100
        )
        capital_limit = min(
            requested_capital,
            max_per_candidate,
            number(budgets["portfolio"]["new_capital_remaining"]),
        )
        quantity = min(
            requested_qty,
            int(capital_limit // max(unit_capital, 1.0)),
        )
        capital = unit_capital * quantity
        final_score = number(
            scores.get("final_portfolio_score")
            or row.final_portfolio_score
        )
        pair_corr = number(
            (payload.get("correlation") or {}).get(
                "portfolio_correlation"
            )
        )
        exposures = (risk.get("payload_json") or {}).get("exposures", {})
        reasons: list[str] = []
        if row.decision == "REJECT":
            reasons.append("PORTFOLIO_DECISION_REJECTED")
        if final_score < number(policy["min_final_portfolio_score"]):
            reasons.append("MINIMUM_PORTFOLIO_SCORE")
        if quantity <= 0:
            reasons.append("INSUFFICIENT_RISK_BUDGET")
        if (
            number((exposures.get("symbol") or {}).get(symbol)) + capital
        ) / net * 100 > number(policy["max_symbol_pct"]):
            reasons.append("SYMBOL_BUDGET_LIMIT")
        if (
            number((exposures.get("sector") or {}).get(sector)) + capital
        ) / net * 100 > number(policy["max_sector_pct"]):
            reasons.append("SECTOR_BUDGET_LIMIT")
        if (
            number((exposures.get("strategy") or {}).get(strategy)) + capital
        ) / net * 100 > number(policy["max_strategy_pct"]):
            reasons.append("STRATEGY_BUDGET_LIMIT")
        if (
            number(risk.get("portfolio_heat_pct"))
            + number(impact.get("marginal_heat_pct"))
            > number(policy["max_portfolio_heat_pct"])
        ):
            reasons.append("PORTFOLIO_HEAT_LIMIT")
        if pair_corr > number(policy["max_pair_correlation"]):
            reasons.append("CORRELATION_LIMIT")
        return {
            "opportunity_id": (
                identity.get("opportunity_id") or row.opportunity_id
            ),
            "institutional_decision_snapshot_id": identity.get(
                "institutional_decision_snapshot_id"
            ),
            "symbol": symbol,
            "sector": sector,
            "strategy": strategy,
            "final_portfolio_score": final_score,
            "portfolio_fit_score": number(
                scores.get("portfolio_fit_score")
            ),
            "opportunity_cost_score": number(
                scores.get("opportunity_cost_score")
            ),
            "recommended_quantity": quantity,
            "recommended_capital": capital,
            "marginal_heat_pct": number(
                impact.get("marginal_heat_pct")
            ),
            "marginal_var_95": number(impact.get("marginal_var_95")),
            "marginal_greeks": impact.get("marginal_greeks") or {},
            "correlation": pair_corr,
            "decision": row.decision,
            "rank": row.rank,
            "explainability": payload.get("explainability") or {},
            "hard_gate_reasons": reasons,
        }

    def _global_universe_authority(
        self,
        session,
        stock_scanner_run_id: str,
        decisions,
        selected,
        optimization_proof: dict,
    ) -> dict:
        """Classify the full current Stock Intelligence authority.

        The ledger makes the global claim auditable: non-materialized, rejected,
        waiting, and executable-now candidates remain visible rather than being
        silently dropped before portfolio ranking.
        """

        stock_rows = list(session.execute(text("""
            SELECT id, symbol, snapshot_timestamp, payload_json
            FROM stock_scanner_candidates
            WHERE scanner_run_id = :scanner_run_id
            ORDER BY symbol
        """), {"scanner_run_id": stock_scanner_run_id}).mappings())
        opportunity_rows = list(session.scalars(
            select(InstitutionalOpportunityModel).where(
                InstitutionalOpportunityModel.stock_scanner_run_id
                == stock_scanner_run_id
            )
        ).all())
        opportunity_by_candidate = {
            str(row.stock_candidate_id or ""): row for row in opportunity_rows
        }
        opportunity_by_symbol = {
            str(row.symbol or "").upper(): row for row in opportunity_rows
        }
        opportunity_ids = [str(row.opportunity_id) for row in opportunity_rows]
        strategy_rows = list(session.scalars(
            select(StrategyCandidateModel).where(
                StrategyCandidateModel.opportunity_id.in_(opportunity_ids)
            )
        ).all()) if opportunity_ids else []
        strategies_by_opportunity: dict[str, list] = {}
        for row in strategy_rows:
            strategies_by_opportunity.setdefault(
                str(row.opportunity_id), []
            ).append(row)
        comparison_by_opportunity = {
            str(row.opportunity_id): row for row in (
                session.scalars(select(StrategyComparisonModel).where(
                    StrategyComparisonModel.opportunity_id.in_(opportunity_ids)
                )).all() if opportunity_ids else []
            )
        }
        contract_rows = list(session.scalars(
            select(ContractRecommendationModel).where(
                ContractRecommendationModel.opportunity_id.in_(opportunity_ids)
            )
        ).all()) if opportunity_ids else []
        contracts_by_opportunity: dict[str, list] = {}
        for row in contract_rows:
            contracts_by_opportunity.setdefault(
                str(row.opportunity_id), []
            ).append(row)
        execution_by_opportunity = {
            str(row.opportunity_id): row for row in (
                session.scalars(select(ExecutionRecommendationModel).where(
                    ExecutionRecommendationModel.opportunity_id.in_(opportunity_ids)
                )).all() if opportunity_ids else []
            )
        }
        decision_by_opportunity = {
            str(row.opportunity_id): row for row in decisions
        }
        selected_ids = {
            str(item["opportunity_id"]) for item in selected
        }
        ranked_sources: list[dict] = []
        for row in stock_rows:
            raw_payload = row.get("payload_json")
            if isinstance(raw_payload, str):
                try:
                    source_payload = json.loads(raw_payload)
                except json.JSONDecodeError:
                    source_payload = {}
            else:
                source_payload = dict(raw_payload or {})
            ranked_sources.append({
                "stock_candidate_id": str(row.get("id") or ""),
                "symbol": str(row.get("symbol") or "").upper(),
                "payload": source_payload,
                "snapshot_timestamp": row.get("snapshot_timestamp"),
                "source_score": self._source_candidate_score(source_payload),
            })
        ranked_sources.sort(
            key=lambda item: (-item["source_score"], item["symbol"])
        )
        ledger: list[dict] = []
        eligibility_service = StockOpportunityEligibilityService()
        terminal_stage_counts: dict[str, int] = {}
        hard_gate_reason_counts: dict[str, int] = {}
        invalid_ready_invariants = 0
        for source_rank, source in enumerate(ranked_sources, 1):
            symbol = source["symbol"]
            opportunity = (
                opportunity_by_candidate.get(source["stock_candidate_id"])
                or opportunity_by_symbol.get(symbol)
            )
            state = (
                "NOT_MATERIALIZED"
                if opportunity is None
                else str(opportunity.state)
            )
            opportunity_id = (
                None if opportunity is None
                else str(opportunity.opportunity_id)
            )
            decision = decision_by_opportunity.get(str(opportunity_id))
            snapshot_timestamp = source["snapshot_timestamp"]
            if hasattr(snapshot_timestamp, "isoformat"):
                snapshot_timestamp = snapshot_timestamp.isoformat()
            eligibility = eligibility_service.evaluate(
                source["payload"],
                snapshot_timestamp=(
                    None if snapshot_timestamp is None
                    else str(snapshot_timestamp)
                ),
            )
            reasons = list(eligibility.reasons)
            reasons.extend(self._source_governance_reasons(source["payload"]))
            reasons = list(dict.fromkeys(reasons))
            oid = str(opportunity_id or "")
            strategies = strategies_by_opportunity.get(oid, [])
            eligible_strategies = [
                item for item in strategies
                if str(item.disposition) == "ELIGIBLE"
            ]
            comparison = comparison_by_opportunity.get(oid)
            selected_strategy_id = (
                None if comparison is None
                else comparison.selected_strategy_candidate_id
            )
            contracts = contracts_by_opportunity.get(oid, [])
            current_contracts = [
                item for item in contracts
                if opportunity is not None
                and str(item.option_snapshot_id or "")
                == str(opportunity.option_snapshot_id or "")
                and str(item.strategy_candidate_id or "")
                == str(selected_strategy_id or "")
                and bool(item.executable)
            ]
            execution = execution_by_opportunity.get(oid)
            trade_builder = classify_trade_builder_authority(
                None if execution is None else execution.payload_json,
                None if execution is None
                else execution.ready_for_trade_builder,
            )
            executable_now = bool(
                state == "READY_FOR_EXECUTION"
                and trade_builder["authorized"]
            )
            if state == "READY_FOR_EXECUTION" and not executable_now:
                terminal_stage = "INVALID_READY_INVARIANT"
                invalid_ready_invariants += 1
                reasons.extend(trade_builder["reason_codes"])
            elif not eligibility.eligible:
                terminal_stage = "SOURCE_INELIGIBLE"
            elif opportunity is None:
                terminal_stage = "NOT_MATERIALIZED_BUG"
                reasons.append(
                    "SOURCE_DID_NOT_MATERIALIZE_INSTITUTIONAL_OPTION_OPPORTUNITY"
                )
            elif not strategies:
                terminal_stage = "NO_STRATEGY_CANDIDATES"
                reasons.append("NO_STRATEGY_CANDIDATES_GENERATED")
            elif not selected_strategy_id:
                terminal_stage = "NO_SELECTED_STRATEGY"
                reasons.append("NO_ELIGIBLE_STRATEGY_SELECTED")
            elif not current_contracts:
                terminal_stage = "NO_EXECUTABLE_CURRENT_CONTRACT"
                reasons.append("NO_EXECUTABLE_CURRENT_CONTRACT")
            elif execution is None:
                terminal_stage = "FINAL_CERTIFICATION_NOT_BUILT"
                reasons.append("EXECUTION_RECOMMENDATION_MISSING")
            elif executable_now:
                terminal_stage = "EXECUTABLE_NOW"
            elif trade_builder["execution_disposition"] == "WAITING_FOR_ENTRY":
                terminal_stage = "WAITING_FOR_ENTRY"
                reasons.extend(trade_builder["reason_codes"])
            elif trade_builder["execution_disposition"] == "REGENERATE_REQUIRED":
                terminal_stage = "REGENERATION_REQUIRED"
                reasons.extend(trade_builder["reason_codes"])
            elif not trade_builder["certification_present"]:
                terminal_stage = "FINAL_CERTIFICATION_MISSING"
                reasons.extend(trade_builder["reason_codes"])
            elif trade_builder["certification_status"] != "PASS":
                terminal_stage = "FINAL_CERTIFICATION_FAILED"
                reasons.extend(trade_builder["reason_codes"])
            else:
                terminal_stage = f"INSTITUTIONAL_OPTIONS_STATE:{state}"
                reasons.extend(trade_builder["reason_codes"])
            reasons = list(dict.fromkeys(reasons))
            terminal_stage_counts[terminal_stage] = (
                terminal_stage_counts.get(terminal_stage, 0) + 1
            )
            for reason in reasons:
                hard_gate_reason_counts[reason] = (
                    hard_gate_reason_counts.get(reason, 0) + 1
                )
            ledger.append({
                "source_rank": source_rank,
                "stock_candidate_id": source["stock_candidate_id"],
                "symbol": symbol,
                "source_score": source["source_score"],
                "source_eligible": eligibility.eligible,
                "source_eligibility_quality": eligibility.opportunity_quality,
                "opportunity_id": opportunity_id,
                "institutional_options_state": state,
                "terminal_stage": terminal_stage,
                "strategy_candidate_count": len(strategies),
                "eligible_strategy_count": len(eligible_strategies),
                "selected_strategy_candidate_id": selected_strategy_id,
                "contract_package_count": len(contracts),
                "executable_current_contract_count": len(current_contracts),
                "trade_builder_authority": trade_builder,
                "executable_now": executable_now,
                "portfolio_decision": (
                    None if decision is None else str(decision.decision)
                ),
                "final_portfolio_score": (
                    None if decision is None
                    else number(decision.final_portfolio_score)
                ),
                "portfolio_rank": (
                    None if decision is None else decision.rank
                ),
                "selected_in_global_optimum": (
                    opportunity_id in selected_ids
                ),
                "hard_gate_reasons": reasons,
            })
        ready_count = sum(
            item["executable_now"] for item in ledger
        )
        unclassified_or_invalid = sum(
            terminal_stage_counts.get(stage, 0)
            for stage in ("NOT_MATERIALIZED_BUG", "INVALID_READY_INVARIANT")
        )
        complete = bool(
            ledger
            and len(ledger) == len(stock_rows)
            and len({item["symbol"] for item in ledger}) == len(ledger)
            and ready_count == len(decisions)
            and all(
                item["opportunity_id"] in decision_by_opportunity
                for item in ledger if item["executable_now"]
            )
            and unclassified_or_invalid == 0
        )
        claim_proven = bool(
            complete and optimization_proof.get("optimality_proven")
        )
        return {
            "version": "M68.2.1.15-GLOBAL-CERTIFIED-CANDIDATE-AUTHORITY-1.0",
            "status": "PROVEN" if claim_proven else "INCOMPLETE",
            "stock_scanner_run_id": stock_scanner_run_id,
            "source_universe_count": len(ledger),
            "materialized_opportunity_count": len(opportunity_rows),
            "executable_now_count": ready_count,
            "portfolio_decision_count": len(decisions),
            "selected_count": len(selected),
            "source_eligible_count": sum(
                bool(item["source_eligible"]) for item in ledger
            ),
            "strategy_package_count": len(strategy_rows),
            "contract_package_count": len(contract_rows),
            "invalid_ready_invariant_count": invalid_ready_invariants,
            "terminal_stage_counts": dict(sorted(terminal_stage_counts.items())),
            "hard_gate_reason_counts": dict(sorted(hard_gate_reason_counts.items())),
            "all_source_candidates_classified": complete,
            "optimality_proven": claim_proven,
            "claim_scope": (
                "GLOBAL_BEST_PORTFOLIO_FEASIBLE_SUBSET_OF_CURRENT_"
                "STOCK_AUTHORITY"
            ),
            "claim": (
                f"All {len(ledger)} current Stock Intelligence candidates were "
                f"classified through explicit stage outcomes; all {ready_count} "
                "final-certified executable-now candidates were "
                "evaluated; the selected subset is the exact maximum-total-"
                "portfolio-score subset under the published constraints."
            ) if claim_proven else None,
            "scope_limitation": (
                "The global claim is limited to current source candidates that "
                "survive the published source, strategy, contract, final-"
                "certification, entry, and portfolio constraints. Every excluded "
                "candidate remains in the stage ledger with governed reason codes."
            ),
            "candidate_ledger": ledger,
        }

    @staticmethod
    def _source_candidate_score(payload: dict) -> float:
        for key in (
            "overall_score", "score", "composite_score", "scanner_score"
        ):
            if payload.get(key) is not None:
                return number(payload.get(key))
        nested = payload.get("scores") or {}
        for key in ("overall_score", "composite_score", "score"):
            if nested.get(key) is not None:
                return number(nested.get(key))
        return 0.0

    @staticmethod
    def _source_governance_reasons(payload: dict) -> list[str]:
        reasons: list[str] = []
        for container in (payload, payload.get("metadata") or {}):
            for key in (
                "rejection_reasons", "validation_reasons",
                "governance_reasons", "exclusion_reasons",
            ):
                value = container.get(key)
                if isinstance(value, (list, tuple)):
                    reasons.extend(str(item) for item in value if item)
                elif value:
                    reasons.append(str(value))
        return list(dict.fromkeys(reasons))

    def _risk_budgets(self, risk: dict, policy: dict) -> dict:
        payload = dict(risk.get("payload_json") or {})
        net = max(number(risk.get("net_liquidation")), 1.0)
        exposures = payload.get("exposures") or {}
        capital = payload.get("capital") or {}
        greeks = payload.get("greeks") or {}
        new_capital_limit = net * number(policy["max_new_capital_pct"]) / 100
        budgets = {
            "portfolio": {
                "net_liquidation": net,
                "portfolio_heat_pct": number(risk.get("portfolio_heat_pct")),
                "portfolio_heat_limit_pct": number(policy["max_portfolio_heat_pct"]),
                "capital_usage_pct": number(capital.get("capital_usage_pct")),
                "new_capital_limit": new_capital_limit,
                "new_capital_remaining": max(0.0, new_capital_limit),
                "buying_power": number(risk.get("buying_power")),
            },
            "limits": {
                "symbol_pct": number(policy["max_symbol_pct"]),
                "sector_pct": number(policy["max_sector_pct"]),
                "strategy_pct": number(policy["max_strategy_pct"]),
                "pair_correlation": number(policy["max_pair_correlation"]),
            },
            "utilization": {
                "symbol": self._dimension_utilization(exposures.get("symbol") or {}, net, policy["max_symbol_pct"]),
                "sector": self._dimension_utilization(exposures.get("sector") or {}, net, policy["max_sector_pct"]),
                "strategy": self._dimension_utilization(exposures.get("strategy") or {}, net, policy["max_strategy_pct"]),
            },
            "greeks": {
                "delta": number(greeks.get("delta")),
                "gamma": number(greeks.get("gamma")),
                "theta": number(greeks.get("theta")),
                "vega": number(greeks.get("vega")),
                "beta_weighted_delta": number(greeks.get("beta_weighted_delta")),
            },
        }
        breaches = []
        for dimension in ("symbol", "sector", "strategy"):
            for name, row in budgets["utilization"][dimension].items():
                if row["utilization_pct"] > 100:
                    breaches.append(f"{dimension.upper()}:{name}")
        if budgets["portfolio"]["portfolio_heat_pct"] > budgets["portfolio"]["portfolio_heat_limit_pct"]:
            breaches.append("PORTFOLIO_HEAT")
        budgets["breaches"] = breaches
        budgets["status"] = "BREACHED" if breaches else "READY"
        utilization_values = [
            row["utilization_pct"]
            for dimension in budgets["utilization"].values()
            for row in dimension.values()
        ]
        budgets["overall_utilization_pct"] = max(utilization_values or [0.0])
        return budgets

    def _dimension_utilization(self, exposure: dict, net: float, limit_pct: float) -> dict:
        output = {}
        for name, value in exposure.items():
            exposure_pct = number(value) / net * 100
            output[str(name)] = {
                "exposure": number(value),
                "exposure_pct": exposure_pct,
                "limit_pct": number(limit_pct),
                "utilization_pct": exposure_pct / max(number(limit_pct), 0.0001) * 100,
                "remaining_pct": max(0.0, number(limit_pct) - exposure_pct),
            }
        return output

    def _hedge_recommendations(self, risk: dict, policy: dict) -> list[dict]:
        payload = dict(risk.get("payload_json") or {})
        greeks = payload.get("greeks") or {}
        net = max(number(risk.get("net_liquidation")), 1.0)
        beta_delta = number(greeks.get("beta_weighted_delta"))
        vega = number(greeks.get("vega"))
        recommendations = []
        beta_pct = abs(beta_delta) / net * 100
        if beta_pct >= number(policy["delta_hedge_threshold_pct"]):
            direction = "BUY_PROTECTIVE_PUT_SPREAD" if beta_delta > 0 else "BUY_CALL_SPREAD_HEDGE"
            recommendations.append({
                "action_key": "HEDGE:BETA_DELTA",
                "action_type": "HEDGE",
                "symbol": "SPY",
                "priority": "HIGH" if beta_pct >= 25 else "MEDIUM",
                "status": "ADVISORY",
                "recommended_action": direction,
                "reason": f"Beta-weighted directional exposure is {beta_pct:.1f}% of net liquidation.",
                "before": {"beta_weighted_delta": beta_delta},
                "target": {"beta_weighted_delta_reduction_pct": 35},
            })
        vega_pct = abs(vega) / net * 100
        if vega_pct >= number(policy["vega_hedge_threshold_pct"]):
            recommendations.append({
                "action_key": "HEDGE:VEGA",
                "action_type": "HEDGE",
                "symbol": "VIX",
                "priority": "MEDIUM",
                "status": "ADVISORY",
                "recommended_action": "REDUCE_LONG_VEGA" if vega > 0 else "ADD_LONG_VEGA",
                "reason": f"Portfolio Vega exposure consumes {vega_pct:.2f}% of net liquidation per IV point.",
                "before": {"vega": vega},
                "target": {"vega_reduction_pct": 25},
            })
        sector_util = self._risk_budgets(risk, policy)["utilization"]["sector"]
        for sector, row in sector_util.items():
            if row["utilization_pct"] >= 90:
                recommendations.append({
                    "action_key": f"HEDGE:SECTOR:{sector}",
                    "action_type": "HEDGE",
                    "symbol": self._sector_proxy(sector),
                    "priority": "HIGH" if row["utilization_pct"] > 100 else "MEDIUM",
                    "status": "ADVISORY",
                    "recommended_action": "SECTOR_DOWNSIDE_HEDGE",
                    "reason": f"{sector} exposure uses {row['utilization_pct']:.1f}% of its risk budget.",
                    "before": row,
                    "target": {"utilization_pct": 75},
                })
        return recommendations

    def _rebalance_recommendations(self, session, portfolio_id, risk, selected, policy):
        actions = []
        budgets = self._risk_budgets(risk, policy)
        positions = list(session.scalars(select(PortfolioPositionModel).where(
            PortfolioPositionModel.portfolio_id == portfolio_id,
            PortfolioPositionModel.status == "OPEN",
        )).all())
        breached_symbols = {
            name for name, row in budgets["utilization"]["symbol"].items()
            if row["utilization_pct"] > 100
        }
        for position in positions:
            if position.symbol in breached_symbols:
                actions.append({
                    "action_key": f"REDUCE:{position.position_id}",
                    "action_type": "REDUCE",
                    "symbol": position.symbol,
                    "priority": "HIGH",
                    "status": "ADVISORY",
                    "position_id": position.position_id,
                    "recommended_action": "SCALE_OUT",
                    "reason": "Symbol exposure exceeds the governed concentration budget.",
                    "target_quantity_reduction_pct": 25,
                })
        for candidate in selected:
            actions.append({
                "action_key": f"ADD:{candidate['opportunity_id']}",
                "action_type": "ADD",
                "symbol": candidate["symbol"],
                "priority": "HIGH" if candidate["rank"] == 1 else "MEDIUM",
                "status": "ADVISORY",
                "opportunity_id": candidate["opportunity_id"],
                "recommended_action": "OPEN_POSITION",
                "recommended_quantity": candidate["recommended_quantity"],
                "recommended_capital": candidate["recommended_capital"],
                "reason": candidate["selection_reason"],
            })
        return actions

    def _target_portfolio(self, risk, selected):
        payload = dict(risk.get("payload_json") or {})
        before_greeks = dict(payload.get("greeks") or {})
        after_greeks = dict(before_greeks)
        marginal_var = marginal_heat = capital = 0.0
        for candidate in selected:
            capital += number(candidate["recommended_capital"])
            marginal_var += number(candidate["marginal_var_95"])
            marginal_heat += number(candidate["marginal_heat_pct"])
            for greek, value in (candidate.get("marginal_greeks") or {}).items():
                after_greeks[greek] = number(after_greeks.get(greek)) + number(value)
        return {
            "selected_opportunity_count": len(selected),
            "recommended_new_capital": capital,
            "before": {
                "greeks": before_greeks,
                "var_95": number(risk.get("var_95")),
                "expected_shortfall_95": number(risk.get("expected_shortfall_95")),
                "portfolio_heat_pct": number(risk.get("portfolio_heat_pct")),
            },
            "after": {
                "greeks": after_greeks,
                "var_95": number(risk.get("var_95")) + marginal_var,
                "expected_shortfall_95": number(risk.get("expected_shortfall_95")) + marginal_var * 1.25,
                "portfolio_heat_pct": number(risk.get("portfolio_heat_pct")) + marginal_heat,
            },
        }

    def _objective(self, selected):
        if not selected:
            return 0.0
        return clamp(sum(number(item["final_portfolio_score"]) for item in selected) / len(selected))

    def _status(self, selected, decisions, budgets, optimization_proof):
        if not optimization_proof.get("optimality_proven"):
            return "FAILED"
        if budgets["status"] == "BREACHED":
            return "DEGRADED"
        if decisions and not selected:
            return "REVIEW"
        return "READY"

    def _selection_reason(self, candidate):
        reasons = [
            f"Portfolio score {candidate['final_portfolio_score']:.1f}",
            f"fit {candidate['portfolio_fit_score']:.1f}",
            f"opportunity cost {candidate['opportunity_cost_score']:.1f}",
        ]
        if candidate["correlation"] < 0.35:
            reasons.append("low portfolio correlation")
        return "; ".join(reasons) + "."

    def _explain(self, selected, rejected, budgets):
        return {
            "summary": (
                f"Exactly selected {len(selected)} candidate(s) from the full "
                "executable-now set under capital, heat, symbol, sector, "
                "strategy, and correlation constraints."
            ),
            "positive_reasons": [item["selection_reason"] for item in selected[:5]],
            "binding_constraints": sorted({
                reason for item in rejected for reason in item.get("rejection_reasons", [])
            }),
            "risk_budget_breaches": budgets.get("breaches", []),
        }

    def _upsert_snapshot(self, session, portfolio_id, risk_snapshot_id, payload, state_hash):
        row = session.scalar(select(PortfolioOptimizationSnapshotModel).where(
            PortfolioOptimizationSnapshotModel.portfolio_id == portfolio_id,
            PortfolioOptimizationSnapshotModel.risk_snapshot_id == risk_snapshot_id,
        ))
        selected = payload["selected_candidates"]
        capital = sum(number(item["recommended_capital"]) for item in selected)
        if row is None:
            row = PortfolioOptimizationSnapshotModel(
                optimization_snapshot_id="M64-OPT-" + uuid4().hex.upper(),
                portfolio_id=portfolio_id,
                risk_snapshot_id=risk_snapshot_id,
                generated_at=utc_now(),
                status=payload["status"],
                objective_score=number(payload["objective"]["score"]),
                selected_count=len(selected),
                recommended_capital=capital,
                state_hash=state_hash,
                payload_json=payload,
            )
            session.add(row)
        else:
            row.generated_at = utc_now(); row.status = payload["status"]
            row.objective_score = number(payload["objective"]["score"])
            row.selected_count = len(selected); row.recommended_capital = capital
            row.state_hash = state_hash; row.payload_json = payload
        session.flush()
        return row

    def _upsert_budget(self, session, portfolio_id, risk_snapshot_id, budgets):
        row = session.scalar(select(PortfolioRiskBudgetSnapshotModel).where(
            PortfolioRiskBudgetSnapshotModel.portfolio_id == portfolio_id,
            PortfolioRiskBudgetSnapshotModel.risk_snapshot_id == risk_snapshot_id,
        ))
        if row is None:
            row = PortfolioRiskBudgetSnapshotModel(
                budget_snapshot_id="M64-BUDGET-" + uuid4().hex.upper(),
                portfolio_id=portfolio_id,
                risk_snapshot_id=risk_snapshot_id,
                generated_at=utc_now(), status=budgets["status"],
                utilization_pct=number(budgets["overall_utilization_pct"]),
                payload_json=budgets,
            )
            session.add(row)
        else:
            row.generated_at=utc_now(); row.status=budgets["status"]
            row.utilization_pct=number(budgets["overall_utilization_pct"])
            row.payload_json=budgets
        session.flush(); return row

    def _upsert_actions(self, session, portfolio_id, risk_snapshot_id, actions):
        persisted=[]
        for action in actions:
            key=str(action["action_key"])
            row=session.scalar(select(PortfolioRecommendationModel).where(
                PortfolioRecommendationModel.portfolio_id==portfolio_id,
                PortfolioRecommendationModel.risk_snapshot_id==risk_snapshot_id,
                PortfolioRecommendationModel.action_key==key,
            ))
            if row is None:
                row=PortfolioRecommendationModel(
                    recommendation_id="M64-ACTION-"+uuid4().hex.upper(),
                    portfolio_id=portfolio_id,risk_snapshot_id=risk_snapshot_id,
                    action_key=key,action_type=str(action["action_type"]),
                    symbol=action.get("symbol"),priority=str(action.get("priority","MEDIUM")),
                    status=str(action.get("status","ADVISORY")),created_at=utc_now(),payload_json=action,
                );session.add(row)
            else:
                row.action_type=str(action["action_type"]);row.symbol=action.get("symbol")
                row.priority=str(action.get("priority","MEDIUM"));row.status=str(action.get("status","ADVISORY"))
                row.created_at=utc_now();row.payload_json=action
            persisted.append(row)
        session.flush();return persisted

    def _upsert_publication(self, session, portfolio_id, risk_snapshot_id, snapshot, payload):
        row=session.scalar(select(PortfolioIntelligencePublicationModel).where(
            PortfolioIntelligencePublicationModel.portfolio_id==portfolio_id,
            PortfolioIntelligencePublicationModel.publication_name==self.PUBLICATION_NAME,
        ))
        if row is None:
            row=PortfolioIntelligencePublicationModel(
                publication_id="M64-PUB-"+uuid4().hex.upper(),publication_name=self.PUBLICATION_NAME,
                portfolio_id=portfolio_id,risk_snapshot_id=risk_snapshot_id,
                optimization_snapshot_id=snapshot.optimization_snapshot_id,published_at=utc_now(),
                status=payload["status"],payload_json=payload,
            );session.add(row)
        else:
            row.risk_snapshot_id=risk_snapshot_id;row.optimization_snapshot_id=snapshot.optimization_snapshot_id
            row.published_at=utc_now();row.status=payload["status"];row.payload_json=payload
        session.flush();return row

    @staticmethod
    def _symbol(payload):
        identity=payload.get("decision_identity") or {}
        return str(payload.get("symbol") or identity.get("symbol") or payload.get("explainability",{}).get("symbol") or "UNKNOWN").upper()

    @staticmethod
    def _sector(payload):
        return str(payload.get("sector") or (payload.get("portfolio_impact") or {}).get("sector") or "UNKNOWN")

    @staticmethod
    def _strategy(payload):
        return str(payload.get("strategy") or payload.get("selected_strategy") or "UNKNOWN")

    @staticmethod
    def _sector_proxy(sector):
        mapping={"Technology":"XLK","Financials":"XLF","Energy":"XLE","Consumer Staples":"XLP","Healthcare":"XLV","Industrials":"XLI","Utilities":"XLU","Real Estate":"XLRE","Crude Oil":"USO"}
        return mapping.get(str(sector),"SPY")
