from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import log
from typing import Any, Iterable

from .profile import stable_hash


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class CandidateOutcomeObservation:
    observation_id: str
    candidate_id: str
    scanner_run_id: str
    symbol: str
    setup_category: str
    market_regime: str
    strategy: str
    direction: str
    published_at: str
    prediction_probability: float
    entry_triggered: bool
    entry_price: float | None = None
    exit_price: float | None = None
    stop_price: float | None = None
    target_prices: list[float] = field(default_factory=list)
    maximum_favorable_excursion_pct: float = 0.0
    maximum_adverse_excursion_pct: float = 0.0
    realized_return_pct: float = 0.0
    option_return_pct: float | None = None
    holding_period_days: float = 0.0
    outcome: str = "OPEN"
    exit_reason: str = ""
    management_policy: str = "DYNAMIC_UNDERLYING"
    state_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def finalize(self) -> "CandidateOutcomeObservation":
        self.prediction_probability = max(0.0, min(1.0, float(self.prediction_probability)))
        self.maximum_favorable_excursion_pct = float(self.maximum_favorable_excursion_pct)
        self.maximum_adverse_excursion_pct = float(self.maximum_adverse_excursion_pct)
        self.realized_return_pct = float(self.realized_return_pct)
        if not self.state_hash:
            payload = asdict(self)
            payload.pop("state_hash", None)
            self.state_hash = stable_hash(payload)
        return self

    @property
    def is_closed(self) -> bool:
        return self.outcome.upper() in {"WIN", "LOSS", "BREAKEVEN", "EXPIRED", "CANCELLED"}

    @property
    def binary_result(self) -> int | None:
        outcome = self.outcome.upper()
        if outcome == "WIN":
            return 1
        if outcome in {"LOSS", "EXPIRED"}:
            return 0
        return None


@dataclass
class OutcomeAttributionProfile:
    key: str
    observation_count: int
    win_count: int
    loss_count: int
    win_rate: float
    expectancy_pct: float
    profit_factor: float | None
    average_mfe_pct: float
    average_mae_pct: float
    average_holding_days: float
    brier_score: float | None
    log_loss: float | None
    calibration_error: float | None
    confidence_grade: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ProbabilityCalibrationBucket:
    lower_bound: float
    upper_bound: float
    observation_count: int
    predicted_probability: float
    realized_win_rate: float
    calibration_error: float


@dataclass
class ProbabilityCalibrationProfile:
    observation_count: int
    brier_score: float | None
    log_loss: float | None
    expected_calibration_error: float | None
    buckets: list[ProbabilityCalibrationBucket] = field(default_factory=list)
    valid: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ManagementPolicyComparison:
    policy_name: str
    observation_count: int
    expectancy_pct: float
    win_rate: float
    average_mfe_capture_pct: float
    average_mae_pct: float
    premature_exit_rate: float
    score: float


class OutcomeTrackingEngine:
    """Creates immutable, point-in-time outcome observations."""

    def create_observation(
        self,
        *,
        candidate_payload: dict[str, Any],
        candidate_id: str,
        scanner_run_id: str,
        outcome: str,
        entry_triggered: bool,
        entry_price: float | None = None,
        exit_price: float | None = None,
        high_price: float | None = None,
        low_price: float | None = None,
        realized_return_pct: float | None = None,
        option_return_pct: float | None = None,
        holding_period_days: float = 0.0,
        exit_reason: str = "",
        management_policy: str = "DYNAMIC_UNDERLYING",
        metadata: dict[str, Any] | None = None,
    ) -> CandidateOutcomeObservation:
        scores = candidate_payload.get("scores") or {}
        trade_plan = candidate_payload.get("trade_plan") or {}
        entry = trade_plan.get("entry") or {}
        stop = trade_plan.get("stop") or {}
        targets = trade_plan.get("targets") or {}
        context = candidate_payload.get("context") or {}

        entry_value = entry_price
        if entry_value is None:
            entry_value = entry.get("preferred_entry")
        entry_value = float(entry_value) if entry_value not in (None, "") else None

        direction = str(candidate_payload.get("direction", "NEUTRAL")).upper()
        bullish = "BULLISH" in direction or str(candidate_payload.get("option_direction", "")).upper() == "CALL"

        mfe = 0.0
        mae = 0.0
        if entry_value and entry_value > 0:
            if high_price is not None and low_price is not None:
                if bullish:
                    mfe = (float(high_price) - entry_value) / entry_value * 100.0
                    mae = (entry_value - float(low_price)) / entry_value * 100.0
                else:
                    mfe = (entry_value - float(low_price)) / entry_value * 100.0
                    mae = (float(high_price) - entry_value) / entry_value * 100.0
            if realized_return_pct is None and exit_price is not None:
                sign = 1.0 if bullish else -1.0
                realized_return_pct = sign * (float(exit_price) - entry_value) / entry_value * 100.0

        raw_probability = candidate_payload.get("underlying_adjusted_probability")
        if raw_probability is None:
            raw_probability = candidate_payload.get("final_calibrated_probability")
        if raw_probability is None:
            raw_probability = candidate_payload.get("probability_of_profit")
        if raw_probability is None:
            raw_probability = scores.get("confidence", 50.0) / 100.0
        probability = float(raw_probability)
        if probability > 1.0:
            probability /= 100.0

        target_prices = []
        for item in targets.get("targets") or []:
            if isinstance(item, dict) and item.get("price") is not None:
                target_prices.append(float(item["price"]))

        return CandidateOutcomeObservation(
            observation_id=stable_hash({
                "candidate_id": candidate_id,
                "scanner_run_id": scanner_run_id,
                "outcome": outcome,
                "exit_reason": exit_reason,
                "exit_price": exit_price,
            })[:32],
            candidate_id=candidate_id,
            scanner_run_id=scanner_run_id,
            symbol=str(candidate_payload.get("symbol", "")).upper(),
            setup_category=str(scores.get("primary_category", candidate_payload.get("primary_category", "UNKNOWN"))).upper(),
            market_regime=str(context.get("market_regime", candidate_payload.get("market_regime", "UNKNOWN"))).upper(),
            strategy=str(candidate_payload.get("recommended_option_strategy", candidate_payload.get("strategy", "UNKNOWN"))).upper(),
            direction=direction,
            published_at=str(candidate_payload.get("snapshot_timestamp") or datetime.now(timezone.utc).isoformat()),
            prediction_probability=probability,
            entry_triggered=bool(entry_triggered),
            entry_price=entry_value,
            exit_price=float(exit_price) if exit_price is not None else None,
            stop_price=float(stop.get("recommended_stop")) if stop.get("recommended_stop") is not None else None,
            target_prices=target_prices,
            maximum_favorable_excursion_pct=round(max(0.0, mfe), 6),
            maximum_adverse_excursion_pct=round(max(0.0, mae), 6),
            realized_return_pct=round(float(realized_return_pct or 0.0), 6),
            option_return_pct=float(option_return_pct) if option_return_pct is not None else None,
            holding_period_days=float(holding_period_days),
            outcome=str(outcome).upper(),
            exit_reason=str(exit_reason).upper(),
            management_policy=str(management_policy).upper(),
            metadata=dict(metadata or {}),
        ).finalize()


class ProbabilityCalibrationEngine:
    def __init__(self, bucket_width: float = 0.10, minimum_observations: int = 20):
        self.bucket_width = float(bucket_width)
        self.minimum_observations = int(minimum_observations)

    def analyze(self, observations: Iterable[CandidateOutcomeObservation]) -> ProbabilityCalibrationProfile:
        closed = [x for x in observations if x.binary_result is not None]
        if not closed:
            return ProbabilityCalibrationProfile(0, None, None, None, valid=False, warnings=["NO_CLOSED_BINARY_OUTCOMES"])

        probs = [max(1e-6, min(1 - 1e-6, x.prediction_probability)) for x in closed]
        actual = [int(x.binary_result) for x in closed]
        brier = sum((p - y) ** 2 for p, y in zip(probs, actual)) / len(closed)
        ll = -sum(y * log(p) + (1 - y) * log(1 - p) for p, y in zip(probs, actual)) / len(closed)

        buckets: list[ProbabilityCalibrationBucket] = []
        width = self.bucket_width
        start = 0.0
        while start < 1.0:
            end = min(1.0, start + width)
            members = [(p, y) for p, y in zip(probs, actual) if start <= p < end or (end == 1.0 and p <= end)]
            if members:
                predicted = sum(p for p, _ in members) / len(members)
                realized = sum(y for _, y in members) / len(members)
                buckets.append(ProbabilityCalibrationBucket(
                    round(start, 4), round(end, 4), len(members), round(predicted, 6), round(realized, 6), round(abs(predicted - realized), 6)
                ))
            start = end

        ece = sum(bucket.observation_count / len(closed) * bucket.calibration_error for bucket in buckets)
        warnings = []
        if len(closed) < self.minimum_observations:
            warnings.append("INSUFFICIENT_CALIBRATION_SAMPLE")
        return ProbabilityCalibrationProfile(
            observation_count=len(closed),
            brier_score=round(brier, 6),
            log_loss=round(ll, 6),
            expected_calibration_error=round(ece, 6),
            buckets=buckets,
            valid=len(closed) >= self.minimum_observations,
            warnings=warnings,
        )


class OutcomeAttributionEngine:
    def summarize(self, observations: Iterable[CandidateOutcomeObservation], group_by: str) -> list[OutcomeAttributionProfile]:
        groups: dict[str, list[CandidateOutcomeObservation]] = {}
        for observation in observations:
            key = str(getattr(observation, group_by, "UNKNOWN") or "UNKNOWN")
            groups.setdefault(key, []).append(observation)
        return [self._profile(key, values) for key, values in sorted(groups.items())]

    def _profile(self, key: str, values: list[CandidateOutcomeObservation]) -> OutcomeAttributionProfile:
        closed = [x for x in values if x.is_closed]
        wins = [x for x in closed if x.outcome == "WIN"]
        losses = [x for x in closed if x.outcome in {"LOSS", "EXPIRED"}]
        returns = [x.realized_return_pct for x in closed]
        gross_profit = sum(max(0.0, x) for x in returns)
        gross_loss = abs(sum(min(0.0, x) for x in returns))
        calibration = ProbabilityCalibrationEngine(minimum_observations=1).analyze(closed)
        count = len(closed)
        win_rate = len(wins) / count * 100.0 if count else 0.0
        expectancy = sum(returns) / count if count else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (None if gross_profit == 0 else float("inf"))
        warnings = []
        if count < 20:
            warnings.append("SMALL_SAMPLE")
        grade = "A" if count >= 100 else "B" if count >= 50 else "C" if count >= 20 else "D"
        return OutcomeAttributionProfile(
            key=key,
            observation_count=count,
            win_count=len(wins),
            loss_count=len(losses),
            win_rate=round(win_rate, 4),
            expectancy_pct=round(expectancy, 6),
            profit_factor=None if profit_factor is None else round(profit_factor, 6),
            average_mfe_pct=round(sum(x.maximum_favorable_excursion_pct for x in closed) / count, 6) if count else 0.0,
            average_mae_pct=round(sum(x.maximum_adverse_excursion_pct for x in closed) / count, 6) if count else 0.0,
            average_holding_days=round(sum(x.holding_period_days for x in closed) / count, 6) if count else 0.0,
            brier_score=calibration.brier_score,
            log_loss=calibration.log_loss,
            calibration_error=calibration.expected_calibration_error,
            confidence_grade=grade,
            warnings=warnings,
        )


class DynamicExitLearningEngine:
    def compare(self, observations: Iterable[CandidateOutcomeObservation]) -> list[ManagementPolicyComparison]:
        groups: dict[str, list[CandidateOutcomeObservation]] = {}
        for observation in observations:
            if observation.is_closed:
                groups.setdefault(observation.management_policy, []).append(observation)
        comparisons: list[ManagementPolicyComparison] = []
        for policy, rows in sorted(groups.items()):
            count = len(rows)
            wins = sum(1 for x in rows if x.outcome == "WIN")
            expectancy = sum(x.realized_return_pct for x in rows) / count
            capture_values = []
            premature = 0
            for x in rows:
                if x.maximum_favorable_excursion_pct > 0:
                    capture_values.append(max(0.0, x.realized_return_pct) / x.maximum_favorable_excursion_pct * 100.0)
                if x.realized_return_pct <= 0 < x.maximum_favorable_excursion_pct:
                    premature += 1
            capture = sum(capture_values) / len(capture_values) if capture_values else 0.0
            mae = sum(x.maximum_adverse_excursion_pct for x in rows) / count
            premature_rate = premature / count * 100.0
            score = _clamp(50.0 + expectancy * 4.0 + capture * 0.25 - mae * 1.5 - premature_rate * 0.15)
            comparisons.append(ManagementPolicyComparison(
                policy_name=policy,
                observation_count=count,
                expectancy_pct=round(expectancy, 6),
                win_rate=round(wins / count * 100.0, 4),
                average_mfe_capture_pct=round(capture, 6),
                average_mae_pct=round(mae, 6),
                premature_exit_rate=round(premature_rate, 6),
                score=round(score, 4),
            ))
        return sorted(comparisons, key=lambda x: (x.score, x.observation_count, x.policy_name), reverse=True)
