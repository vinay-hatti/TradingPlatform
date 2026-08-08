from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import log
from statistics import mean
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from .domain import deterministic_hash
from .models import (
    InstitutionalOptionLearningSnapshotModel,
    InstitutionalOptionOutcomeObservationModel,
    InstitutionalOpportunityModel,
    OpportunityThesisModel,
    StrategyCandidateModel,
    StrategyValuationModel,
)


@dataclass(frozen=True)
class OutcomeObservationInput:
    opportunity_id: str
    entry_timestamp: str
    exit_timestamp: str
    underlying_entry: float
    underlying_exit: float
    option_entry_value: float
    option_exit_value: float
    quantity: float
    exit_reason: str
    mfe_pct: float | None = None
    mae_pct: float | None = None
    management_policy: str = "UNDERLYING_DYNAMIC"
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class OutcomeCaptureResult:
    observation_id: str
    opportunity_id: str
    outcome: str
    realized_return_pct: float
    realized_pnl: float
    predicted_probability: float | None
    state_hash: str


@dataclass(frozen=True)
class LearningSummary:
    learning_snapshot_id: str
    observation_count: int
    win_rate: float | None
    expectancy_pct: float | None
    profit_factor: float | None
    brier_score: float | None
    log_loss: float | None
    expected_calibration_error: float | None
    warnings: tuple[str, ...]
    state_hash: str


def _bounded_probability(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.001, min(0.999, float(value)))


def _calibration_buckets(rows: Iterable[InstitutionalOptionOutcomeObservationModel]) -> list[dict[str, Any]]:
    buckets: list[dict[str, Any]] = []
    data = [row for row in rows if row.predicted_probability is not None]
    for lower in range(0, 100, 10):
        upper = lower + 10
        subset = [row for row in data if lower / 100 <= float(row.predicted_probability) < upper / 100]
        if not subset:
            continue
        actual = mean(1.0 if row.outcome == "WIN" else 0.0 for row in subset)
        predicted = mean(float(row.predicted_probability) for row in subset)
        buckets.append({
            "lower": lower / 100,
            "upper": upper / 100,
            "count": len(subset),
            "predicted": predicted,
            "actual": actual,
            "absolute_error": abs(actual - predicted),
        })
    return buckets


class InstitutionalOptionsOutcomeLearningService:
    POLICY_VERSION = "m62-outcome-learning-v1"

    def __init__(self, session: Session):
        self.session = session

    def capture(self, item: OutcomeObservationInput) -> OutcomeCaptureResult:
        opportunity = self.session.get(InstitutionalOpportunityModel, item.opportunity_id)
        if opportunity is None:
            raise LookupError(f"Institutional option opportunity not found: {item.opportunity_id}")
        existing = self.session.query(InstitutionalOptionOutcomeObservationModel).filter_by(
            opportunity_id=item.opportunity_id
        ).first()
        if existing is not None:
            raise ValueError("An immutable outcome observation already exists for this opportunity")

        valuation = self.session.query(StrategyValuationModel).filter_by(
            opportunity_id=item.opportunity_id, selected=True
        ).first()
        strategy = None
        if valuation is not None:
            strategy = self.session.get(StrategyCandidateModel, valuation.strategy_candidate_id)
        thesis = self.session.query(OpportunityThesisModel).filter_by(
            opportunity_id=item.opportunity_id
        ).first()

        option_entry = float(item.option_entry_value)
        option_exit = float(item.option_exit_value)
        if option_entry <= 0:
            raise ValueError("option_entry_value must be positive")
        quantity = float(item.quantity)
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        return_pct = (option_exit - option_entry) / option_entry * 100.0
        pnl = (option_exit - option_entry) * quantity * 100.0
        outcome = "WIN" if return_pct > 0 else "LOSS" if return_pct < 0 else "FLAT"
        predicted = _bounded_probability(None if valuation is None else valuation.calibrated_probability)
        observation_id = f"m62-outcome-{uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "observation_id": observation_id,
            "opportunity_id": item.opportunity_id,
            "symbol": opportunity.symbol,
            "setup_category": opportunity.category,
            "direction": opportunity.direction,
            "market_regime": None if thesis is None else (thesis.payload_json or {}).get("market_regime"),
            "strategy_candidate_id": None if strategy is None else strategy.strategy_candidate_id,
            "strategy": None if strategy is None else strategy.strategy,
            "predicted_probability": predicted,
            "entry_timestamp": item.entry_timestamp,
            "exit_timestamp": item.exit_timestamp,
            "underlying_entry": float(item.underlying_entry),
            "underlying_exit": float(item.underlying_exit),
            "option_entry_value": option_entry,
            "option_exit_value": option_exit,
            "quantity": quantity,
            "realized_return_pct": return_pct,
            "realized_pnl": pnl,
            "outcome": outcome,
            "exit_reason": item.exit_reason,
            "mfe_pct": item.mfe_pct,
            "mae_pct": item.mae_pct,
            "management_policy": item.management_policy,
            "metadata": dict(item.metadata or {}),
            "captured_at": now,
            "policy_version": self.POLICY_VERSION,
        }
        state_hash = deterministic_hash(payload)
        payload["state_hash"] = state_hash
        row = InstitutionalOptionOutcomeObservationModel(
            observation_id=observation_id,
            opportunity_id=item.opportunity_id,
            strategy_candidate_id=payload["strategy_candidate_id"],
            setup_category=opportunity.category,
            market_regime=payload["market_regime"],
            management_policy=item.management_policy,
            predicted_probability=predicted,
            realized_return_pct=return_pct,
            realized_pnl=pnl,
            outcome=outcome,
            exit_reason=item.exit_reason,
            entry_timestamp=item.entry_timestamp,
            exit_timestamp=item.exit_timestamp,
            payload_json=payload,
        )
        self.session.add(row)
        self.session.flush()
        return OutcomeCaptureResult(observation_id, item.opportunity_id, outcome, return_pct, pnl, predicted, state_hash)

    def summarize(self, *, scope: str = "ALL", scope_value: str | None = None) -> LearningSummary:
        query = self.session.query(InstitutionalOptionOutcomeObservationModel)
        scope_upper = scope.upper()
        if scope_upper == "STRATEGY" and scope_value:
            query = query.join(StrategyCandidateModel, StrategyCandidateModel.strategy_candidate_id == InstitutionalOptionOutcomeObservationModel.strategy_candidate_id).filter(StrategyCandidateModel.strategy == scope_value)
        elif scope_upper == "SETUP" and scope_value:
            query = query.filter(InstitutionalOptionOutcomeObservationModel.setup_category == scope_value)
        elif scope_upper == "REGIME" and scope_value:
            query = query.filter(InstitutionalOptionOutcomeObservationModel.market_regime == scope_value)
        elif scope_upper == "MANAGEMENT" and scope_value:
            query = query.filter(InstitutionalOptionOutcomeObservationModel.management_policy == scope_value)
        rows = query.order_by(InstitutionalOptionOutcomeObservationModel.exit_timestamp.asc()).all()
        count = len(rows)
        returns = [float(row.realized_return_pct) for row in rows]
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        win_rate = None if not count else len(wins) / count
        expectancy = None if not count else mean(returns)
        profit_factor = None
        if losses:
            profit_factor = sum(wins) / abs(sum(losses)) if wins else 0.0
        calibrated = [(float(row.predicted_probability), 1.0 if row.outcome == "WIN" else 0.0) for row in rows if row.predicted_probability is not None and row.outcome in {"WIN", "LOSS"}]
        brier = None if not calibrated else mean((p - y) ** 2 for p, y in calibrated)
        logloss = None if not calibrated else -mean(y * log(max(p, 0.001)) + (1 - y) * log(max(1 - p, 0.001)) for p, y in calibrated)
        buckets = _calibration_buckets(rows)
        ece = None
        if calibrated and buckets:
            ece = sum(bucket["count"] / len(calibrated) * bucket["absolute_error"] for bucket in buckets)
        warnings: list[str] = []
        if count < 30:
            warnings.append("SMALL_SAMPLE_SIZE")
        if len(calibrated) < 20:
            warnings.append("INSUFFICIENT_CALIBRATION_SAMPLE")
        snapshot_id = f"m62-learning-{uuid4().hex}"
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "learning_snapshot_id": snapshot_id,
            "scope": scope_upper,
            "scope_value": scope_value,
            "observation_count": count,
            "win_rate": win_rate,
            "expectancy_pct": expectancy,
            "profit_factor": profit_factor,
            "brier_score": brier,
            "log_loss": logloss,
            "expected_calibration_error": ece,
            "calibration_buckets": buckets,
            "average_mfe_pct": None if not rows else mean(float(row.payload_json.get("mfe_pct") or 0.0) for row in rows),
            "average_mae_pct": None if not rows else mean(float(row.payload_json.get("mae_pct") or 0.0) for row in rows),
            "warnings": warnings,
            "policy_version": self.POLICY_VERSION,
            "created_at": now,
        }
        state_hash = deterministic_hash(payload)
        payload["state_hash"] = state_hash
        self.session.add(InstitutionalOptionLearningSnapshotModel(
            learning_snapshot_id=snapshot_id,
            scope=scope_upper,
            scope_value=scope_value,
            observation_count=count,
            win_rate=win_rate,
            expectancy_pct=expectancy,
            brier_score=brier,
            expected_calibration_error=ece,
            created_at=now,
            payload_json=payload,
        ))
        self.session.flush()
        return LearningSummary(snapshot_id, count, win_rate, expectancy, profit_factor, brier, logloss, ece, tuple(warnings), state_hash)
