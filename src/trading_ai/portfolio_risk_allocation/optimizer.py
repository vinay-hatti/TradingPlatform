from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import select

from trading_ai.portfolio_management.database_models import PortfolioPositionModel

from .decision_intelligence import InstitutionalDecisionIntelligenceService
from .models import (
    PortfolioDecisionIntelligenceModel,
    PortfolioIntelligencePublicationModel,
    PortfolioOptimizationSnapshotModel,
    PortfolioRecommendationModel,
    PortfolioRiskBudgetSnapshotModel,
)
from .service import PortfolioRiskAllocationService, clamp, number


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PortfolioOptimizationService:
    """Governed, deterministic portfolio optimizer and recommendation publisher.

    The optimizer deliberately uses a transparent constrained-greedy policy rather
    than an opaque mathematical solver.  Every selected or rejected candidate is
    accompanied by the binding constraints and portfolio contribution that drove
    the result.  Future learning modules may replace the objective weights while
    retaining this contract.
    """

    POLICY_VERSION = "M64-PORTFOLIO-OPTIMIZER-1.0"
    PUBLICATION_NAME = "current_portfolio_allocation"

    DEFAULT_POLICY = {
        "max_new_positions": 5,
        "max_new_capital_pct": 5.0,
        "max_single_candidate_capital_pct": 2.0,
        "max_portfolio_heat_pct": 20.0,
        "max_symbol_pct": 10.0,
        "max_sector_pct": 25.0,
        "max_strategy_pct": 35.0,
        "max_pair_correlation": 0.80,
        "min_final_portfolio_score": 62.0,
        "max_candidates_considered": 250,
        "delta_hedge_threshold_pct": 15.0,
        "vega_hedge_threshold_pct": 0.75,
    }

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.risk_service = PortfolioRiskAllocationService(session_factory)
        self.decision_service = InstitutionalDecisionIntelligenceService(session_factory)

    def build(
        self,
        portfolio_id: str = "PAPER-PRIMARY",
        *,
        rebuild_decisions: bool = True,
        actor: str = "m64-portfolio-optimizer",
        policy: dict | None = None,
    ) -> dict:
        policy_values = {**self.DEFAULT_POLICY, **(policy or {})}
        risk = self.risk_service.current(portfolio_id) or self.risk_service.build(portfolio_id, actor)
        if rebuild_decisions:
            self.decision_service.build(
                portfolio_id,
                limit=int(policy_values["max_candidates_considered"]),
            )

        with self.session_factory() as session:
            decisions = list(
                session.scalars(
                    select(PortfolioDecisionIntelligenceModel)
                    .where(
                        PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id,
                        PortfolioDecisionIntelligenceModel.risk_snapshot_id == risk["snapshot_id"],
                    )
                    .order_by(
                        PortfolioDecisionIntelligenceModel.final_portfolio_score.desc(),
                        PortfolioDecisionIntelligenceModel.rank.asc(),
                    )
                ).all()
            )
            risk_payload = dict(risk.get("payload_json") or {})
            budgets = self._risk_budgets(risk, policy_values)
            selected, rejected = self._select_candidates(decisions, risk, budgets, policy_values)
            hedge_recommendations = self._hedge_recommendations(risk, policy_values)
            rebalance_recommendations = self._rebalance_recommendations(
                session, portfolio_id, risk, selected, policy_values
            )
            target = self._target_portfolio(risk, selected)
            objective = self._objective(selected)
            status = self._status(selected, decisions, budgets)
            payload = {
                "policy_version": self.POLICY_VERSION,
                "generated_by": actor,
                "portfolio_id": portfolio_id,
                "risk_snapshot_id": risk["snapshot_id"],
                "generated_at": utc_now(),
                "status": status,
                "objective": {
                    "name": "MAXIMIZE_EXPECTED_PORTFOLIO_IMPROVEMENT",
                    "score": objective,
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
                "best_next_trades": selected[:5],
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
            session.commit()
            return {
                **payload,
                "optimization_snapshot_id": snapshot.optimization_snapshot_id,
                "budget_snapshot_id": budget_row.budget_snapshot_id,
                "publication_id": publication.publication_id,
                "persisted_action_count": len(action_rows),
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
        selected: list[dict] = []
        rejected: list[dict] = []
        net = max(number(risk.get("net_liquidation")), 1.0)
        remaining_capital = budgets["portfolio"]["new_capital_remaining"]
        current_heat = number(risk.get("portfolio_heat_pct"))
        selected_symbols: set[str] = set()
        selected_sectors: dict[str, float] = {}
        selected_strategies: dict[str, float] = {}

        for row in decisions:
            payload = dict(row.payload_json or {})
            identity = payload.get("decision_identity") or {}
            symbol = self._symbol(payload)
            sector = self._sector(payload)
            strategy = self._strategy(payload)
            allocation = payload.get("capital_allocation") or {}
            impact = payload.get("portfolio_impact") or {}
            scores = payload.get("scores") or {}
            requested_qty = max(0, int(number(allocation.get("recommended_quantity"))))
            unit_capital = number(allocation.get("recommended_capital")) / max(requested_qty, 1)
            max_per_candidate = net * number(policy["max_single_candidate_capital_pct"]) / 100
            candidate_capital = min(
                number(allocation.get("recommended_capital")),
                max_per_candidate,
                remaining_capital,
            )
            quantity = min(requested_qty, int(candidate_capital // max(unit_capital, 1.0)))
            final_score = number(scores.get("final_portfolio_score") or row.final_portfolio_score)
            reasons: list[str] = []
            if row.decision == "REJECT":
                reasons.append("PORTFOLIO_DECISION_REJECTED")
            if final_score < number(policy["min_final_portfolio_score"]):
                reasons.append("MINIMUM_PORTFOLIO_SCORE")
            if quantity <= 0:
                reasons.append("INSUFFICIENT_RISK_BUDGET")
            if len(selected) >= int(policy["max_new_positions"]):
                reasons.append("MAX_NEW_POSITIONS")
            if symbol in selected_symbols:
                reasons.append("DUPLICATE_SYMBOL_ALLOCATION")
            projected_heat = current_heat + sum(number(x["marginal_heat_pct"]) for x in selected) + number(impact.get("marginal_heat_pct"))
            if projected_heat > number(policy["max_portfolio_heat_pct"]):
                reasons.append("PORTFOLIO_HEAT_LIMIT")
            projected_sector = number(selected_sectors.get(sector)) + candidate_capital
            current_sector = number((risk.get("payload_json") or {}).get("exposures", {}).get("sector", {}).get(sector))
            if (current_sector + projected_sector) / net * 100 > number(policy["max_sector_pct"]):
                reasons.append("SECTOR_BUDGET_LIMIT")
            projected_strategy = number(selected_strategies.get(strategy)) + candidate_capital
            current_strategy = number((risk.get("payload_json") or {}).get("exposures", {}).get("strategy", {}).get(strategy))
            if (current_strategy + projected_strategy) / net * 100 > number(policy["max_strategy_pct"]):
                reasons.append("STRATEGY_BUDGET_LIMIT")
            pair_corr = number((payload.get("correlation") or {}).get("portfolio_correlation"))
            if pair_corr > number(policy["max_pair_correlation"]):
                reasons.append("CORRELATION_LIMIT")

            candidate = {
                "opportunity_id": identity.get("opportunity_id") or row.opportunity_id,
                "institutional_decision_snapshot_id": identity.get("institutional_decision_snapshot_id"),
                "symbol": symbol,
                "sector": sector,
                "strategy": strategy,
                "final_portfolio_score": final_score,
                "portfolio_fit_score": number(scores.get("portfolio_fit_score")),
                "opportunity_cost_score": number(scores.get("opportunity_cost_score")),
                "recommended_quantity": quantity,
                "recommended_capital": unit_capital * quantity,
                "marginal_heat_pct": number(impact.get("marginal_heat_pct")),
                "marginal_var_95": number(impact.get("marginal_var_95")),
                "marginal_greeks": impact.get("marginal_greeks") or {},
                "correlation": pair_corr,
                "decision": row.decision,
                "rank": row.rank,
                "explainability": payload.get("explainability") or {},
            }
            if reasons:
                candidate["rejection_reasons"] = reasons
                candidate["optimizer_decision"] = "SKIP"
                rejected.append(candidate)
                continue
            candidate["optimizer_decision"] = "SELECT"
            candidate["selection_reason"] = self._selection_reason(candidate)
            selected.append(candidate)
            selected_symbols.add(symbol)
            selected_sectors[sector] = number(selected_sectors.get(sector)) + candidate["recommended_capital"]
            selected_strategies[strategy] = number(selected_strategies.get(strategy)) + candidate["recommended_capital"]
            remaining_capital -= candidate["recommended_capital"]

        return selected, rejected

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

    def _status(self, selected, decisions, budgets):
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
                f"Selected {len(selected)} candidate(s) under capital, heat, concentration, "
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
