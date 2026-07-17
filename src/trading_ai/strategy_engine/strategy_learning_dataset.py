from __future__ import annotations

from datetime import date, datetime
from math import isfinite
from typing import Any, Iterable

from trading_ai.strategy_engine.strategy_learning_policy import StrategyLearningPolicy
from trading_ai.strategy_engine.strategy_learning_profile import StrategyOutcomeRecord


class StrategyLearningDatasetBuilder:
    """Normalize completed trade outcomes into governed learning records."""

    def __init__(self, policy: StrategyLearningPolicy | None = None):
        self.policy = policy or StrategyLearningPolicy()

    @staticmethod
    def _value(obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            result = float(value)
            return result if isfinite(result) else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _date(value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if value in (None, ""):
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def build(self, outcomes: Iterable[Any], as_of_date: date | None = None) -> tuple[StrategyOutcomeRecord, ...]:
        as_of = as_of_date or date.today()
        records: list[StrategyOutcomeRecord] = []
        for item in outcomes:
            strategy = str(self._value(item, "strategy", "") or "").upper()
            outcome_date = self._date(
                self._value(item, "outcome_date", self._value(item, "exit_date", self._value(item, "date", None)))
            )
            if not strategy or outcome_date is None:
                if self.policy.reject_invalid_records:
                    continue
                strategy = strategy or "UNKNOWN"
                outcome_date = outcome_date or as_of
            age = (as_of - outcome_date).days
            if age < 0 or age > self.policy.maximum_history_days:
                continue
            realized_return = self._float(
                self._value(item, "realized_return", self._value(item, "return_pct", self._value(item, "net_return", 0.0)))
            )
            limit = abs(float(self.policy.winsorize_return_pct))
            realized_return = min(max(realized_return, -limit), limit)
            pnl = self._float(self._value(item, "pnl", self._value(item, "net_pnl", 0.0)))
            won_raw = self._value(item, "won", None)
            won = bool(won_raw) if won_raw is not None else (pnl > 0.0 or realized_return > 0.0)
            records.append(
                StrategyOutcomeRecord(
                    strategy=strategy,
                    outcome_date=outcome_date,
                    realized_return=realized_return,
                    pnl=pnl,
                    won=won,
                    symbol=str(self._value(item, "symbol", "") or ""),
                    direction=str(self._value(item, "direction", "NEUTRAL") or "NEUTRAL").upper(),
                    market_regime=str(self._value(item, "market_regime", "UNKNOWN") or "UNKNOWN").upper(),
                    volatility_regime=str(self._value(item, "volatility_regime", "UNKNOWN") or "UNKNOWN").upper(),
                    calibration_score=self._float(self._value(item, "calibration_score", 50.0), 50.0),
                    execution_score=self._float(self._value(item, "execution_score", 50.0), 50.0),
                    metadata=dict(self._value(item, "metadata", {}) or {}),
                )
            )
        return tuple(sorted(records, key=lambda record: (record.strategy, record.outcome_date)))
