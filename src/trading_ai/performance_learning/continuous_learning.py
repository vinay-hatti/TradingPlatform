from __future__ import annotations

from datetime import datetime, timezone
from math import log
from statistics import mean
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from trading_ai.execution_intelligence.models import ExecutionLearningSampleModel, ExecutionOrderTelemetryModel
from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.execution_workspace.models import ExecutionIntentModel
from trading_ai.broker.ibkr.database_models import BrokerExecutionModel, BrokerOrderModel
from trading_ai.institutional_options.models import InstitutionalDecisionSnapshotModel, InstitutionalOpportunityModel
from trading_ai.opex_intelligence.models import (
    OpexForecastOutcomeModel,
    OpexForecastPublicationModel,
    OpexForecastSnapshotModel,
)
from trading_ai.database.models import PriceHistory
from .models import (
    CalibrationRunModel,
    ExecutionQualityAnalyticsModel,
    PredictionOutcomeModel,
    PredictionRegistryModel,
    TradeOutcomeModel,
    PerformanceObservationModel,
)

VERSION = "M72.2.1-EVIDENCE-INTEGRITY-HARDENING-1.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex.upper()}"


def _clip01(value: float | None) -> float | None:
    if value is None:
        return None
    return min(0.999999, max(0.000001, float(value)))


def _prob(value: float | None) -> float | None:
    if value is None:
        return None
    value = float(value)
    return _clip01(value / 100.0 if value > 1.0 else value)


def _mean(values: list[float]) -> float:
    return round(mean(values), 6) if values else 0.0


def calibration_metrics(samples: list[tuple[float, int]]) -> dict:
    if not samples:
        return {
            "sample_size": 0,
            "brier_score": None,
            "log_loss": None,
            "expected_calibration_error": None,
            "buckets": [],
        }
    brier = mean((p - y) ** 2 for p, y in samples)
    ll = mean(-(y * log(p) + (1 - y) * log(1 - p)) for p, y in samples)
    buckets = []
    for lower in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        upper = lower + 0.1
        rows = [(p, y) for p, y in samples if (lower <= p < upper) or (upper >= 1 and lower <= p <= 1)]
        if not rows:
            continue
        predicted = mean(p for p, _ in rows)
        observed = mean(y for _, y in rows)
        buckets.append(
            {
                "lower": lower,
                "upper": min(1.0, upper),
                "count": len(rows),
                "predicted": round(predicted, 6),
                "observed": round(observed, 6),
                "calibration_error": round(abs(predicted - observed), 6),
            }
        )
    ece = sum(x["count"] * x["calibration_error"] for x in buckets) / len(samples)
    return {
        "sample_size": len(samples),
        "brier_score": round(brier, 6),
        "log_loss": round(ll, 6),
        "expected_calibration_error": round(ece, 6),
        "buckets": buckets,
    }


class ContinuousLearningService:
    """Governed prediction -> outcome -> calibration learning loop.

    The service never changes model weights autonomously. It records immutable
    predictions, realizes observable outcomes, computes calibration/quality
    analytics, and publishes evidence for human-governed learning policies.
    """

    def __init__(self, session: Session):
        self.s = session

    def capture_predictions(self, portfolio_id: str = "PAPER-PRIMARY") -> dict:
        created = existing = 0

        decisions = list(self.s.scalars(select(InstitutionalDecisionSnapshotModel)))
        opportunities = {x.opportunity_id:x for x in self.s.scalars(select(InstitutionalOpportunityModel))}
        for d in decisions:
            source_id = f"TRADE:{d.decision_snapshot_id}"
            if self.s.scalar(select(PredictionRegistryModel).where(PredictionRegistryModel.source_id == source_id)):
                existing += 1
                continue
            payload = dict(d.payload_json or {})
            prob = _prob(d.calibrated_probability)
            features = {
                "institutional_score": d.institutional_score,
                "selected_strategy": d.selected_strategy,
                "expected_value": d.expected_value,
                "capital_required": d.capital_required,
                "market_regime": ((payload.get("underlying_thesis") or {}).get("market_regime") or "UNKNOWN"),
                "state_hash": d.state_hash,
            }
            self.s.add(PredictionRegistryModel(
                prediction_id=_id("M72-PRED"), source_type="TRADE_DECISION", source_id=source_id,
                portfolio_id=portfolio_id, symbol=str((opportunities.get(d.opportunity_id).symbol if opportunities.get(d.opportunity_id) else None) or payload.get("symbol") or payload.get("underlying_symbol") or "UNKNOWN"),
                strategy=d.selected_strategy, target_type="TRADE_WIN", predicted_probability=prob,
                confidence=_prob(payload.get("confidence") or payload.get("decision_confidence")),
                model_version=d.policy_version, generated_at=d.created_at, horizon_end=None,
                features_json=features,
                prediction_json={"probability": prob, "expected_value": d.expected_value, "institutional_score": d.institutional_score},
                lineage_json={"opportunity_id": d.opportunity_id, "decision_snapshot_id": d.decision_snapshot_id,
                              "strategy_candidate_id": d.strategy_candidate_id, "contract_recommendation_id": d.contract_recommendation_id},
            ))
            created += 1

        publication = self.s.scalar(
            select(OpexForecastPublicationModel).where(
                OpexForecastPublicationModel.publication_name
                == "current_opex_intelligence"
            )
        )
        published_forecast_ids = list(
            ((publication.payload_json or {}).get("forecast_ids") or [])
            if publication
            else []
        )
        forecasts = list(
            self.s.scalars(
                select(OpexForecastSnapshotModel).where(
                    OpexForecastSnapshotModel.forecast_id.in_(
                        published_forecast_ids
                    )
                )
            )
        ) if published_forecast_ids else []
        for f in forecasts:
            source_id = f"OPEX:{f.forecast_id}"
            if self.s.scalar(select(PredictionRegistryModel).where(PredictionRegistryModel.source_id == source_id)):
                existing += 1
                continue
            p = dict(f.payload_json or {})
            scenarios = p.get("scenarios") or []
            dominant = max(scenarios, key=lambda x: float(x.get("probability", 0) or 0), default={})
            self.s.add(PredictionRegistryModel(
                prediction_id=_id("M72-PRED"), source_type="OPEX_FORECAST", source_id=source_id,
                portfolio_id=None, symbol=f.symbol, strategy=None, target_type="OPEX_SCENARIO",
                predicted_probability=_prob(dominant.get("probability")), confidence=_prob(f.confidence),
                model_version=str(p.get("version") or "M71"), generated_at=f.forecast_timestamp, horizon_end=f.expiration,
                features_json={"dte": f.dte, "cycle_type": f.cycle_type, "dealer_pressure": f.dealer_pressure,
                               "confidence": f.confidence, "dominant_scenario": dominant.get("name"),
                               "magnet": f.magnet, "support": f.support, "resistance": f.resistance},
                prediction_json={"dominant_scenario": dominant, "ranges": {
                    "50": [f.range50_low, f.range50_high], "68": [f.range68_low, f.range68_high], "90": [f.range90_low, f.range90_high]},
                    "magnet": p.get("magnet"), "actionable_range": p.get("actionable_range"),
                    "expected_daily_path": p.get("expected_daily_path", []), "levels": (p.get("path_distribution") or {}).get("levels", [])},
                lineage_json={"forecast_id": f.forecast_id, "expiration": f.expiration, "forecast_timestamp": f.forecast_timestamp,
                              "input_fingerprint": f.input_fingerprint,
                              "publication_id": publication.publication_id if publication else None,
                              "governance": {"runtime_mode": "SHADOW", "authority_effect": False}},
            ))
            created += 1

        self.s.commit()
        return {"created": created, "existing": existing, "version": VERSION}

    def bridge_trade_outcomes(self, portfolio_id: str = "PAPER-PRIMARY") -> dict:
        """Bridge M65 reconstructed closed outcomes into the legacy observation stream.

        This makes the existing Performance tab and M58/M65 report path consume the
        same realized evidence as M72 without inventing or duplicating outcomes.
        """
        from .outcome_engine import Milestone65LearningService

        reconstruction = Milestone65LearningService(self.s).reconstruct_outcomes(portfolio_id)
        rows = list(self.s.scalars(select(TradeOutcomeModel).where(TradeOutcomeModel.portfolio_id == portfolio_id)))
        created = existing = pending = 0
        for row in rows:
            if row.outcome not in {"WIN", "LOSS", "FLAT"} or not row.closed_at:
                pending += 1
                continue
            found = self.s.scalar(
                select(PerformanceObservationModel).where(
                    PerformanceObservationModel.position_id == row.position_id,
                    PerformanceObservationModel.position_version == row.position_version,
                )
            )
            if found is not None:
                existing += 1
                continue
            payload = dict(row.payload_json or {})
            self.s.add(PerformanceObservationModel(
                observation_id=_id("M72-OBS"),
                position_id=row.position_id,
                position_version=row.position_version,
                portfolio_id=row.portfolio_id,
                opportunity_id=row.opportunity_id,
                strategy=row.strategy,
                direction=str(payload.get("direction") or "UNKNOWN"),
                opened_at=row.opened_at,
                closed_at=row.closed_at,
                predicted_probability=float(_prob(row.predicted_probability) or 0.5),
                realized_return_pct=float(row.realized_return_pct),
                outcome=row.outcome,
                payload_json={
                    **payload,
                    "source": "M72.2_TRADE_OUTCOME_BRIDGE",
                    "trade_outcome_id": row.outcome_id,
                    "decision_snapshot_id": row.decision_snapshot_id,
                    "expected_value": row.expected_value,
                    "realized_pnl": row.realized_pnl,
                    "maximum_drawdown_pct": row.maximum_drawdown_pct,
                    "holding_days": row.holding_days,
                    "market_regime": row.market_regime,
                    "decision_followed": payload.get("decision_followed", True),
                },
                observed_at=row.closed_at or row.reconstructed_at,
            ))
            created += 1
        self.s.commit()
        return {
            "reconstruction": reconstruction,
            "trade_outcomes": len(rows),
            "observations_created": created,
            "observations_existing": existing,
            "pending_open_outcomes": pending,
        }

    def backfill_execution_evidence(self, portfolio_id: str = "PAPER-PRIMARY") -> dict:
        """Backfill M70 telemetry/learning from already-persisted broker orders.

        This method is intentionally offline: it never connects to IBKR. It bridges
        existing execution_intents + broker_orders into execution telemetry and
        terminal learning samples. A separate optional broker synchronization can be
        run before this when historical executions need to be imported from IBKR.
        """
        from trading_ai.execution_intelligence.service import ExecutionIntelligenceService

        intents = list(self.s.scalars(select(ExecutionIntentModel).where(ExecutionIntentModel.portfolio_id == portfolio_id)))
        orders = list(self.s.scalars(select(BrokerOrderModel).where(BrokerOrderModel.portfolio_id == portfolio_id)))
        order_by_aggregate = {str(x.aggregate_id): x for x in orders}
        before_telemetry = {x.execution_intent_id for x in self.s.scalars(select(ExecutionOrderTelemetryModel))}
        before_samples = {x.execution_intent_id for x in self.s.scalars(select(ExecutionLearningSampleModel))}
        matched = not_routed = routed_without_persisted_order = errors = 0
        terminal = filled_orders = 0
        svc = ExecutionIntelligenceService(self.s)
        for intent in intents:
            aggregate = str((intent.broker_json or {}).get("aggregate_id") or f"M59-{intent.execution_intent_id}")
            broker = order_by_aggregate.get(aggregate)
            if broker is None:
                # An intent that never reached submission is not missing broker evidence.
                # Count only submitted/routed intents as an evidence-integrity gap.
                if intent.submitted_at or str(intent.state or "").upper() in {"SUBMITTED", "PRESUBMITTED", "AWAITING_BROKER_ACK", "FILLED", "CANCELLED", "CANCELED", "INACTIVE"}:
                    routed_without_persisted_order += 1
                else:
                    not_routed += 1
                continue
            matched += 1
            status = str(broker.status or "").upper()
            if status in {"FILLED", "CANCELLED", "CANCELED", "REJECTED", "INACTIVE"}:
                terminal += 1
            if status == "FILLED" or float(broker.filled_quantity or 0) > 0 or float(broker.average_fill_price or 0) > 0:
                filled_orders += 1
            try:
                svc.record_broker_sync(intent, broker)
            except Exception:
                self.s.rollback()
                errors += 1
        after_telemetry = {x.execution_intent_id for x in self.s.scalars(select(ExecutionOrderTelemetryModel))}
        after_samples = {x.execution_intent_id for x in self.s.scalars(select(ExecutionLearningSampleModel))}
        broker_execution_count = len(list(self.s.scalars(select(BrokerExecutionModel).where(BrokerExecutionModel.portfolio_id == portfolio_id))))
        return {
            "execution_intents": len(intents),
            "broker_orders": len(orders),
            "matched_orders": matched,
            "not_routed_intents": not_routed,
            "routed_without_persisted_order": routed_without_persisted_order,
            "missing_orders": routed_without_persisted_order,
            "terminal_orders": terminal,
            "filled_orders": filled_orders,
            "telemetry_created": len(after_telemetry - before_telemetry),
            "learning_samples_created": len(after_samples - before_samples),
            "broker_executions": broker_execution_count,
            "errors": errors,
            "mode": "PERSISTED_EVIDENCE_ONLY",
        }

    def realize_outcomes(self, portfolio_id: str = "PAPER-PRIMARY") -> dict:
        created = existing = pending = 0
        predictions = list(self.s.scalars(select(PredictionRegistryModel)))
        trade_rows = list(self.s.scalars(select(TradeOutcomeModel).where(TradeOutcomeModel.portfolio_id == portfolio_id)))
        trade_by_decision = {x.decision_snapshot_id: x for x in trade_rows if x.decision_snapshot_id}
        trade_by_opportunity = {}
        for row in trade_rows:
            # Prefer a closed/final result when multiple position versions exist.
            prior = trade_by_opportunity.get(row.opportunity_id)
            if prior is None or (row.outcome in {"WIN", "LOSS", "FLAT"} and prior.outcome not in {"WIN", "LOSS", "FLAT"}) or row.position_version > prior.position_version:
                trade_by_opportunity[row.opportunity_id] = row
        opex_by_forecast = {x.forecast_id: x for x in self.s.scalars(select(OpexForecastOutcomeModel))}
        for pred in predictions:
            if pred.source_type == "TRADE_DECISION":
                lineage = pred.lineage_json or {}
                opportunity_id = lineage.get("opportunity_id")
                decision_snapshot_id = lineage.get("decision_snapshot_id")
                observed = trade_by_decision.get(decision_snapshot_id) or trade_by_opportunity.get(opportunity_id)
                if not observed or observed.outcome not in {"WIN", "LOSS", "FLAT"}:
                    pending += 1
                    continue
                outcome_type = "TRADE_WIN"
                if self.s.scalar(select(PredictionOutcomeModel).where(PredictionOutcomeModel.prediction_id == pred.prediction_id, PredictionOutcomeModel.outcome_type == outcome_type)):
                    existing += 1
                    continue
                y = 1 if observed.realized_return_pct > 0 else 0
                self.s.add(PredictionOutcomeModel(
                    outcome_id=_id("M72-OUT"), prediction_id=pred.prediction_id, outcome_type=outcome_type,
                    binary_outcome=y, realized_value=observed.realized_return_pct,
                    error_value=None if pred.predicted_probability is None else abs(pred.predicted_probability - y),
                    realized_at=observed.closed_at or observed.reconstructed_at,
                    outcome_json={"realized_pnl": observed.realized_pnl, "realized_return_pct": observed.realized_return_pct,
                                  "maximum_drawdown_pct": observed.maximum_drawdown_pct, "holding_days": observed.holding_days,
                                  "outcome": observed.outcome},
                )); created += 1
            elif pred.source_type == "OPEX_FORECAST":
                forecast_id = (pred.lineage_json or {}).get("forecast_id")
                observed = opex_by_forecast.get(forecast_id)
                if not observed:
                    pending += 1
                    continue
                metrics = {
                    "OPEX_RANGE_50": int(observed.in_50), "OPEX_RANGE_68": int(observed.in_68), "OPEX_RANGE_90": int(observed.in_90),
                }
                extra = dict(observed.payload_json or {})
                if extra.get("in_actionable_range") is not None: metrics["OPEX_ACTIONABLE_RANGE"] = int(extra["in_actionable_range"])
                if extra.get("in_magnet_zone") is not None: metrics["OPEX_MAGNET_ZONE"] = int(extra["in_magnet_zone"])
                for outcome_type, y in metrics.items():
                    if self.s.scalar(select(PredictionOutcomeModel).where(PredictionOutcomeModel.prediction_id == pred.prediction_id, PredictionOutcomeModel.outcome_type == outcome_type)):
                        existing += 1; continue
                    self.s.add(PredictionOutcomeModel(
                        outcome_id=_id("M72-OUT"), prediction_id=pred.prediction_id, outcome_type=outcome_type,
                        binary_outcome=y, realized_value=observed.settlement_price,
                        error_value=observed.magnet_distance_pct if outcome_type == "OPEX_MAGNET_ZONE" else None,
                        realized_at=observed.realized_at,
                        outcome_json={"settlement_price": observed.settlement_price, "magnet_distance_pct": observed.magnet_distance_pct, **extra},
                    )); created += 1
                prediction_json=pred.prediction_json or {}; features=pred.features_json or {}
                dominant=((prediction_json.get("dominant_scenario") or {}).get("name") or features.get("dominant_scenario") or "UNKNOWN")
                settle=float(observed.settlement_price);support=features.get("support");resistance=features.get("resistance")
                if not observed.in_90: actual_scenario="VOLATILITY_SHOCK"
                elif extra.get("in_actionable_range") or extra.get("in_magnet_zone"): actual_scenario="PIN_RANGE"
                elif resistance is not None and settle>float(resistance): actual_scenario="BULLISH_BREAKOUT"
                elif support is not None and settle<float(support): actual_scenario="BEARISH_BREAKDOWN"
                else: actual_scenario="PIN_RANGE"
                outcome_type="OPEX_SCENARIO"
                if not self.s.scalar(select(PredictionOutcomeModel).where(PredictionOutcomeModel.prediction_id==pred.prediction_id,PredictionOutcomeModel.outcome_type==outcome_type)):
                    self.s.add(PredictionOutcomeModel(outcome_id=_id("M72-OUT"),prediction_id=pred.prediction_id,outcome_type=outcome_type,binary_outcome=1 if dominant==actual_scenario else 0,realized_value=settle,error_value=None,realized_at=observed.realized_at,outcome_json={"predicted_scenario":dominant,"actual_scenario":actual_scenario,"settlement_price":settle}));created+=1
                daily=prediction_json.get("expected_daily_path") or []
                if daily and not self.s.scalar(select(PredictionOutcomeModel).where(PredictionOutcomeModel.prediction_id==pred.prediction_id,PredictionOutcomeModel.outcome_type=="OPEX_PATH")):
                    dates=[str(x.get("date")) for x in daily if x.get("date")]; actual_rows=list(self.s.scalars(select(PriceHistory).where(PriceHistory.symbol==pred.symbol,PriceHistory.date.in_(dates)))) if dates else []
                    actual_by={str(x.date):float(x.close) for x in actual_rows};errors=[];pct_errors=[];band_hits=[];direction_hits=[];prev_actual=None;prev_median=None
                    for drow in daily:
                        day=str(drow.get("date"));actual=actual_by.get(day);median_value=drow.get("median",drow.get("expected"));p25=drow.get("p25");p75=drow.get("p75")
                        if actual is None or median_value is None:continue
                        med=float(median_value);errors.append(abs(actual-med));pct_errors.append(abs(actual-med)/max(abs(actual),1e-9)*100)
                        if p25 is not None and p75 is not None:band_hits.append(1 if float(p25)<=actual<=float(p75) else 0)
                        if prev_actual is not None and prev_median is not None:direction_hits.append(1 if (actual-prev_actual)*(med-prev_median)>=0 else 0)
                        prev_actual=actual;prev_median=med
                    if errors:
                        self.s.add(PredictionOutcomeModel(outcome_id=_id("M72-OUT"),prediction_id=pred.prediction_id,outcome_type="OPEX_PATH",binary_outcome=None,realized_value=_mean(pct_errors),error_value=_mean(errors),realized_at=observed.realized_at,outcome_json={"days_evaluated":len(errors),"mae_points":_mean(errors),"mape_pct":_mean(pct_errors),"p25_p75_coverage_pct":round(mean(band_hits)*100,2) if band_hits else None,"direction_accuracy_pct":round(mean(direction_hits)*100,2) if direction_hits else None}));created+=1
        self.s.commit()
        return {"created": created, "existing": existing, "pending": pending}

    def _prediction_samples(self) -> list[dict]:
        preds = {x.prediction_id: x for x in self.s.scalars(select(PredictionRegistryModel))}
        out = []
        for o in self.s.scalars(select(PredictionOutcomeModel)):
            p = preds.get(o.prediction_id)
            if not p:
                continue
            probability = p.predicted_probability
            # Coverage targets carry their semantic probability even though the dominant OPEX scenario has a different probability.
            semantic = {"OPEX_RANGE_50": .50, "OPEX_RANGE_68": .68, "OPEX_RANGE_90": .90}.get(o.outcome_type)
            if semantic is not None: probability = semantic
            if probability is None or o.binary_outcome is None:
                continue
            out.append({"prediction": p, "outcome": o, "probability": _clip01(probability), "y": int(o.binary_outcome)})
        return out

    def build_calibration(self) -> dict:
        rows = self._prediction_samples()
        groups: dict[tuple[str, str, str], list[dict]] = {}
        for row in rows:
            p = row["prediction"]
            keys = [
                ("GLOBAL", "ALL", row["outcome"].outcome_type),
                ("SOURCE", p.source_type, row["outcome"].outcome_type),
                ("MODEL_VERSION", p.model_version, row["outcome"].outcome_type),
                ("SYMBOL", p.symbol, row["outcome"].outcome_type),
            ]
            if p.strategy: keys.append(("STRATEGY", p.strategy, row["outcome"].outcome_type))
            regime = (p.features_json or {}).get("market_regime")
            if regime: keys.append(("MARKET_REGIME", str(regime), row["outcome"].outcome_type))
            for key in keys: groups.setdefault(key, []).append(row)
        generated = _now(); snapshots=[]
        for (scope, value, target), items in groups.items():
            metrics = calibration_metrics([(x["probability"], x["y"]) for x in items])
            row = CalibrationRunModel(
                calibration_run_id=_id("M72-CAL"), scope=scope, scope_value=value, target_type=target,
                sample_size=metrics["sample_size"], brier_score=metrics["brier_score"], log_loss=metrics["log_loss"],
                expected_calibration_error=metrics["expected_calibration_error"], calibration_slope=None, calibration_intercept=None,
                generated_at=generated, metrics_json=metrics,
            ); self.s.add(row); snapshots.append({"scope":scope,"scope_value":value,"target_type":target,**metrics})
        self.s.commit()
        return {"generated_at": generated, "groups": snapshots, "sample_size": len(rows)}

    def execution_quality(self, portfolio_id: str = "PAPER-PRIMARY", persist: bool = True) -> dict:
        rows = list(self.s.scalars(select(ExecutionOrderTelemetryModel)))
        terminal = [x for x in rows if str(x.state).upper() in {"FILLED", "CANCELLED", "CANCELED", "REJECTED", "INACTIVE"}]
        filled = [x for x in rows if x.average_fill_price is not None and x.filled_quantity > 0]
        plans = {x.trade_plan_id:x for x in self.s.scalars(select(TradePlanModel))}
        decisions = {x.opportunity_id:x for x in self.s.scalars(select(InstitutionalDecisionSnapshotModel))}
        slippage=[];qualities=[];delays=[];decision_delays=[];edge_preservation=[];edge_drag=[];by_strategy={}
        for x in terminal:
            qualities.append(float(x.execution_quality_score or 0))
        for x in filled:
            if x.realized_slippage_pct is not None: slippage.append(float(x.realized_slippage_pct))
            try:
                a=datetime.fromisoformat((x.first_submitted_at or '').replace('Z','+00:00'));b=datetime.fromisoformat((x.first_fill_at or x.filled_at or '').replace('Z','+00:00'));delays.append(max(0,(b-a).total_seconds()))
            except Exception: pass
            plan=plans.get(x.trade_plan_id);decision=decisions.get(plan.opportunity_id) if plan else None
            if decision and x.first_submitted_at:
                try:
                    d0=datetime.fromisoformat(decision.created_at.replace('Z','+00:00'));ds=datetime.fromisoformat(x.first_submitted_at.replace('Z','+00:00'));decision_delays.append(max(0,(ds-d0).total_seconds()))
                except Exception: pass
            reference=float(x.fresh_midpoint_price or x.approved_reference_price or x.submitted_limit_price or 0)
            fill=float(x.average_fill_price or 0);adverse_pct=0.0
            if reference>1e-9:
                credit=bool(plan and float(plan.estimated_credit or 0)>float(plan.estimated_debit or 0))
                adverse=(reference-fill) if credit else (fill-reference)
                adverse_pct=max(0.0,adverse/reference*100)
            expected_edge=abs(float(decision.expected_value or 0)) if decision else 0.0
            contracts=max(float(x.filled_quantity or 0),1.0);drag_dollars=max(0.0,fill-reference if not (plan and float(plan.estimated_credit or 0)>float(plan.estimated_debit or 0)) else reference-fill)*100*contracts
            if expected_edge>1e-9:
                preserve=max(0.0,min(100.0,(expected_edge-drag_dollars)/expected_edge*100))
            else:
                preserve=max(0.0,100.0-adverse_pct*10.0)
            edge_preservation.append(preserve);edge_drag.append(drag_dollars)
            d=by_strategy.setdefault(x.strategy,{"n":0,"quality":[],"slippage":[],"preservation":[]});d["n"]+=1;d["quality"].append(float(x.execution_quality_score or 0));d["preservation"].append(preserve)
            if x.realized_slippage_pct is not None:d["slippage"].append(float(x.realized_slippage_pct))
        fill_rate=sum(1 for x in terminal if str(x.state).upper()=="FILLED")/max(len(terminal),1)*100
        summary={
            "sample_size":len(terminal),"filled":len(filled),"fill_rate_pct":round(fill_rate,2),
            "average_quality_score":round(mean(qualities),2) if qualities else 0.0,
            "average_realized_slippage_pct":round(mean(slippage),6) if slippage else 0.0,
            "average_time_to_first_fill_seconds":round(mean(delays),2) if delays else 0.0,
            "median_time_to_first_fill_seconds":round(sorted(delays)[len(delays)//2],2) if delays else 0.0,
            "average_decision_to_submit_seconds":round(mean(decision_delays),2) if decision_delays else 0.0,
            "commission_total":round(sum(float(x.commission_total or 0) for x in terminal),4),
            "edge_preservation_pct":round(mean(edge_preservation),2) if edge_preservation else 0.0,
            "average_execution_edge_drag_dollars":round(mean(edge_drag),4) if edge_drag else 0.0,
            "by_strategy":{k:{"sample_size":v["n"],"average_quality":round(mean(v["quality"]),2) if v["quality"] else 0,"average_slippage_pct":round(mean(v["slippage"]),6) if v["slippage"] else 0,"edge_preservation_pct":round(mean(v["preservation"]),2) if v["preservation"] else 0} for k,v in by_strategy.items()},
        }
        if persist:
            self.s.add(ExecutionQualityAnalyticsModel(execution_quality_snapshot_id=_id("M72-EXECQ"),portfolio_id=portfolio_id,generated_at=_now(),sample_size=summary["sample_size"],average_quality_score=summary["average_quality_score"],average_slippage_pct=summary["average_realized_slippage_pct"],edge_preservation_pct=summary["edge_preservation_pct"],fill_rate_pct=summary["fill_rate_pct"],metrics_json=summary));self.s.commit()
        return summary

    def opex_calibration(self) -> dict:
        from trading_ai.opex_intelligence.service import OpexIntelligenceService

        summary = OpexIntelligenceService(lambda: self.s)._calibration(self.s)
        summary["actionable_range_hit_rate"] = summary.get(
            "actionable_range_coverage"
        )
        return summary

    def dashboard(self, portfolio_id: str = "PAPER-PRIMARY") -> dict:
        predictions = list(self.s.scalars(select(PredictionRegistryModel).order_by(PredictionRegistryModel.generated_at.desc())))
        outcomes = list(self.s.scalars(select(PredictionOutcomeModel)))
        outcome_by_prediction: dict[str, list[PredictionOutcomeModel]] = {}
        for row in outcomes:
            outcome_by_prediction.setdefault(row.prediction_id, []).append(row)
        realized_ids = set(outcome_by_prediction)

        source_counts: dict[str, int] = {}
        target_counts: dict[str, int] = {}
        for row in predictions:
            source_counts[row.source_type] = source_counts.get(row.source_type, 0) + 1
            target_counts[row.target_type] = target_counts.get(row.target_type, 0) + 1

        recent_predictions = []
        for row in predictions[:40]:
            row_outcomes = outcome_by_prediction.get(row.prediction_id, [])
            recent_predictions.append({
                "prediction_id": row.prediction_id,
                "source_type": row.source_type,
                "symbol": row.symbol,
                "strategy": row.strategy,
                "target_type": row.target_type,
                "predicted_probability": row.predicted_probability,
                "confidence": row.confidence,
                "model_version": row.model_version,
                "generated_at": row.generated_at,
                "horizon_end": row.horizon_end,
                "status": "REALIZED" if row.prediction_id in realized_ids else "PENDING",
                "outcomes": [{
                    "outcome_type": x.outcome_type,
                    "binary_outcome": x.binary_outcome,
                    "realized_value": x.realized_value,
                    "error_value": x.error_value,
                    "realized_at": x.realized_at,
                } for x in row_outcomes],
            })

        # Keep only the newest calibration record for each governed segment.
        latest_rows = list(self.s.scalars(select(CalibrationRunModel).order_by(CalibrationRunModel.generated_at.desc())))
        latest_cal = []
        seen = set()
        for row in latest_rows:
            key = (row.scope, row.scope_value, row.target_type)
            if key in seen:
                continue
            seen.add(key); latest_cal.append(row)
            if len(latest_cal) >= 200:
                break

        calibration_rows = []
        reviewable = developing = insufficient = 0
        for x in latest_cal:
            if x.sample_size >= 50:
                health = "REVIEWABLE"; reviewable += 1
            elif x.sample_size >= 30:
                health = "DEVELOPING"; developing += 1
            else:
                health = "INSUFFICIENT_SAMPLE"; insufficient += 1
            metrics = dict(x.metrics_json or {})
            buckets = metrics.get("buckets") or []
            bias = None
            if buckets and x.sample_size:
                bias = sum(float(b.get("count", 0)) * (float(b.get("observed", 0)) - float(b.get("predicted", 0))) for b in buckets) / max(x.sample_size, 1)
            calibration_rows.append({
                "scope": x.scope, "scope_value": x.scope_value, "target_type": x.target_type,
                "sample_size": x.sample_size, "brier_score": x.brier_score, "log_loss": x.log_loss,
                "expected_calibration_error": x.expected_calibration_error, "generated_at": x.generated_at,
                "health": health, "calibration_bias": round(bias, 6) if bias is not None else None, "metrics": metrics,
            })

        opex_summary = self.opex_calibration()
        opex_rows = list(self.s.scalars(select(OpexForecastOutcomeModel).order_by(OpexForecastOutcomeModel.realized_at.desc())))
        opex_by_symbol: dict[str, list[OpexForecastOutcomeModel]] = {}
        for row in opex_rows:
            opex_by_symbol.setdefault(row.symbol, []).append(row)
        scenario_outcomes = [x for x in outcomes if x.outcome_type == "OPEX_SCENARIO"]
        scenario_pred = {x.prediction_id: x for x in predictions if x.source_type == "OPEX_FORECAST"}
        path_outcomes = [x for x in outcomes if x.outcome_type == "OPEX_PATH"]
        path_pred = {x.prediction_id: x for x in predictions if x.source_type == "OPEX_FORECAST"}
        by_symbol = {}
        for symbol, rows in sorted(opex_by_symbol.items()):
            s_scenario = [x for x in scenario_outcomes if scenario_pred.get(x.prediction_id) and scenario_pred[x.prediction_id].symbol == symbol and x.binary_outcome is not None]
            s_path = [x for x in path_outcomes if path_pred.get(x.prediction_id) and path_pred[x.prediction_id].symbol == symbol]
            pp = [x.outcome_json or {} for x in s_path]
            by_symbol[symbol] = {
                "sample_size": len(rows),
                "coverage50": round(mean(x.in_50 for x in rows) * 100, 2),
                "coverage68": round(mean(x.in_68 for x in rows) * 100, 2),
                "coverage90": round(mean(x.in_90 for x in rows) * 100, 2),
                "average_magnet_distance_pct": round(mean(float(x.magnet_distance_pct) for x in rows if x.magnet_distance_pct is not None), 4) if any(x.magnet_distance_pct is not None for x in rows) else None,
                "scenario_accuracy_pct": round(mean(x.binary_outcome for x in s_scenario) * 100, 2) if s_scenario else None,
                "path_mape_pct": round(mean(float(x.get("mape_pct") or 0) for x in pp), 4) if pp else None,
                "path_band_coverage_pct": round(mean(float(x.get("p25_p75_coverage_pct") or 0) for x in pp), 2) if pp else None,
            }
        opex_summary["by_symbol"] = by_symbol
        opex_summary["recent_outcomes"] = [{
            "forecast_id": x.forecast_id, "symbol": x.symbol, "expiration": x.expiration,
            "settlement_price": x.settlement_price, "in_50": bool(x.in_50), "in_68": bool(x.in_68),
            "in_90": bool(x.in_90), "magnet_distance_pct": x.magnet_distance_pct, "realized_at": x.realized_at,
            "in_actionable_range": (x.payload_json or {}).get("in_actionable_range"),
            "in_magnet_zone": (x.payload_json or {}).get("in_magnet_zone"),
        } for x in opex_rows[:20]]

        execq = self.execution_quality(portfolio_id, persist=False)
        trade_outcomes = list(self.s.scalars(select(TradeOutcomeModel).where(TradeOutcomeModel.portfolio_id == portfolio_id)))
        observations = list(self.s.scalars(select(PerformanceObservationModel).where(PerformanceObservationModel.portfolio_id == portfolio_id)))
        execution_intents = list(self.s.scalars(select(ExecutionIntentModel).where(ExecutionIntentModel.portfolio_id == portfolio_id)))
        broker_orders = list(self.s.scalars(select(BrokerOrderModel).where(BrokerOrderModel.portfolio_id == portfolio_id)))
        broker_executions = list(self.s.scalars(select(BrokerExecutionModel).where(BrokerExecutionModel.portfolio_id == portfolio_id)))
        telemetry_rows = list(self.s.scalars(select(ExecutionOrderTelemetryModel)) )
        learning_samples = list(self.s.scalars(select(ExecutionLearningSampleModel)))
        opex_forecasts = list(self.s.scalars(select(OpexForecastSnapshotModel)))
        opex_outcomes = list(self.s.scalars(select(OpexForecastOutcomeModel)))
        realized_trade_outcomes = [x for x in trade_outcomes if x.outcome in {"WIN", "LOSS", "FLAT"} and x.closed_at]
        terminal_broker_orders = [x for x in broker_orders if str(x.status or "").upper() in {"FILLED", "CANCELLED", "CANCELED", "REJECTED", "INACTIVE"}]
        filled_broker_orders = [x for x in broker_orders if str(x.status or "").upper() == "FILLED" or float(x.filled_quantity or 0) > 0 or float(x.average_fill_price or 0) > 0]
        telemetry_ids = {x.execution_intent_id for x in telemetry_rows}
        routed_states = {"SUBMITTED", "PRESUBMITTED", "AWAITING_BROKER_ACK", "FILLED", "CANCELLED", "CANCELED", "INACTIVE"}
        never_routed_intents = [x for x in execution_intents if x.execution_intent_id not in telemetry_ids and not x.submitted_at and str(x.state or "").upper() not in routed_states]
        routed_without_telemetry = [x for x in execution_intents if x.execution_intent_id not in telemetry_ids and (x.submitted_at or str(x.state or "").upper() in routed_states)]
        if filled_broker_orders and not broker_executions:
            broker_execution_sync_state = "EXECUTION_HISTORY_INCOMPLETE"
        elif broker_executions:
            broker_execution_sync_state = "EXECUTIONS_AVAILABLE"
        else:
            broker_execution_sync_state = "NO_FILLS_AVAILABLE"
        evidence_pipeline = {
            "trade": {
                "trade_outcomes": len(trade_outcomes),
                "realized_trade_outcomes": len(realized_trade_outcomes),
                "learning_observations": len(observations),
                "unbridged_realized_outcomes": max(0, len(realized_trade_outcomes) - len(observations)),
            },
            "execution": {
                "execution_intents": len(execution_intents),
                "broker_orders": len(broker_orders),
                "terminal_broker_orders": len(terminal_broker_orders),
                "broker_executions": len(broker_executions),
                "telemetry_rows": len(telemetry_rows),
                "learning_samples": len(learning_samples),
                "filled_broker_orders": len(filled_broker_orders),
                "never_routed_intents": len(never_routed_intents),
                "routed_without_telemetry": len(routed_without_telemetry),
                "broker_execution_sync_state": broker_execution_sync_state,
                "needs_ibkr_execution_sync": broker_execution_sync_state == "EXECUTION_HISTORY_INCOMPLETE",
            },
            "opex": {
                "forecast_snapshots": len(opex_forecasts),
                "forecast_outcomes": len(opex_outcomes),
                "pending_forecasts": max(0, len(opex_forecasts) - len(opex_outcomes)),
            },
        }
        prediction_count = len(predictions)
        realized_predictions = len(realized_ids)
        completion = (realized_predictions / prediction_count * 100.0) if prediction_count else 0.0
        return {
            "version": VERSION,
            "prediction_registry": {
                "predictions": prediction_count, "realized_predictions": realized_predictions,
                "realized_outcomes": len(outcomes), "pending": max(0, prediction_count - realized_predictions),
                "completion_rate_pct": round(completion, 2), "by_source": source_counts, "by_target": target_counts,
                "recent": recent_predictions,
            },
            "calibration": {
                "latest": calibration_rows,
                "health": {"reviewable": reviewable, "developing": developing, "insufficient_sample": insufficient, "segments": len(calibration_rows)},
            },
            "opex_calibration": opex_summary,
            "execution_quality": execq,
            "evidence_pipeline": evidence_pipeline,
            "governance": {
                "automatic_weight_activation": False, "minimum_sample_for_review": 30,
                "minimum_sample_for_segmented_calibration": 50, "learning_mode": "EVIDENCE_ONLY_UNTIL_HUMAN_APPROVAL",
                "evidence_readiness": {"reviewable_segments": reviewable, "developing_segments": developing, "insufficient_segments": insufficient},
            },
        }

    def run_cycle(self, portfolio_id: str = "PAPER-PRIMARY") -> dict:
        trade_bridge = self.bridge_trade_outcomes(portfolio_id)
        # Realize expired OPEX snapshots before translating them into M72 prediction outcomes.
        try:
            from trading_ai.database.session import SessionLocal
            from trading_ai.opex_intelligence.service import OpexIntelligenceService
            opex_realization = OpexIntelligenceService(SessionLocal).realize_outcomes()
        except Exception as exc:
            opex_realization = {"status": "FAILED", "created": 0, "error": f"{type(exc).__name__}: {exc}"}
        execution_bridge = self.backfill_execution_evidence(portfolio_id)
        capture = self.capture_predictions(portfolio_id)
        realize = self.realize_outcomes(portfolio_id)
        cal = self.build_calibration()
        execq = self.execution_quality(portfolio_id)
        opex = self.opex_calibration()
        try:
            from trading_ai.outcome_probability.service import OutcomeProbabilityService
            outcome_probability = OutcomeProbabilityService(self.s).materialize_outcomes()
        except Exception as exc:
            self.s.rollback()
            outcome_probability = {
                "status": "DEFERRED_NON_BLOCKING",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "authority_effect": False,
            }
        return {
            "version": VERSION, "status": "READY",
            "trade_evidence": trade_bridge, "opex_realization": opex_realization, "execution_evidence": execution_bridge,
            "captured": capture, "realized": realize,
            "calibration": {"sample_size": cal["sample_size"], "groups": len(cal["groups"])},
            "execution_quality": execq, "opex_calibration": opex,
            "outcome_probability": outcome_probability,
            "governance": {"automatic_activation": False, "broker_sync_mode": "EXPLICIT_ONLY"},
        }
