from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable, List, Sequence

import numpy as np

from trading_ai.strategy_engine.market_regime_policy import (
    MarketRegimePolicy,
)
from trading_ai.strategy_engine.market_regime_profile import (
    MarketRegimeProfile,
    MarketRegimeTransition,
)


class MarketRegimeEngine:
    """Deterministic institutional market-regime detector."""

    def __init__(self, policy: MarketRegimePolicy | None = None):
        self.policy = policy or MarketRegimePolicy()

    def analyze(
        self,
        prices: Any,
        symbol: str = "UNKNOWN",
    ) -> MarketRegimeProfile:
        close = self._close_values(prices)
        profile = MarketRegimeProfile(
            symbol=str(symbol or "UNKNOWN"),
            observation_count=int(close.size),
        )

        if close.size < self.policy.minimum_observations:
            profile.allowed = not self.policy.reject_invalid_profile
            profile.valid = False
            profile.regime_severity = "MODERATE"
            profile.warnings.append("INSUFFICIENT_REGIME_OBSERVATIONS")
            if self.policy.reject_invalid_profile:
                profile.rejection_reasons.append(
                    "INSUFFICIENT_REGIME_OBSERVATIONS"
                )
            profile.metadata["minimum_observations"] = (
                self.policy.minimum_observations
            )
            return profile

        if np.any(~np.isfinite(close)) or np.any(close <= 0.0):
            profile.allowed = not self.policy.reject_invalid_profile
            profile.valid = False
            profile.regime_severity = "SEVERE"
            profile.warnings.append("INVALID_PRICE_HISTORY")
            if self.policy.reject_invalid_profile:
                profile.rejection_reasons.append("INVALID_PRICE_HISTORY")
            return profile

        returns = np.diff(np.log(close))
        history = self._rolling_regimes(close)
        current = history[-1] if history else "UNKNOWN"
        previous = self._previous_distinct(history, current)
        duration = self._duration(history, current)
        transitions = self._transitions(history)

        short_return = self._period_return(
            close,
            self.policy.short_window,
        )
        medium_return = self._period_return(
            close,
            self.policy.medium_window,
        )
        long_return = self._period_return(
            close,
            self.policy.long_window,
        )
        annualized_volatility = self._annualized_volatility(returns)
        drawdowns = self._drawdown_series(close)
        current_drawdown = float(drawdowns[-1])
        maximum_drawdown = float(np.min(drawdowns))

        trend_score = self._trend_score(
            short_return,
            medium_return,
            long_return,
        )
        volatility_score = self._volatility_score(annualized_volatility)
        momentum_score = self._momentum_score(
            short_return,
            medium_return,
        )
        drawdown_score = self._drawdown_score(current_drawdown)
        stability_score = self._stability_score(history)
        confidence_score = self._confidence_score(
            trend_score=trend_score,
            volatility_score=volatility_score,
            momentum_score=momentum_score,
            drawdown_score=drawdown_score,
            stability_score=stability_score,
            current_regime=current,
        )
        regime_score = self._regime_score(
            confidence_score,
            stability_score,
            current,
        )
        severity = self._severity(
            current,
            annualized_volatility,
            current_drawdown,
        )
        grade = self._grade(regime_score)

        profile.current_regime = current
        profile.previous_regime = previous
        profile.regime_duration = duration
        profile.transition_detected = bool(
            previous != "UNKNOWN" and previous != current
        )
        profile.trend_score = trend_score
        profile.volatility_score = volatility_score
        profile.momentum_score = momentum_score
        profile.drawdown_score = drawdown_score
        profile.stability_score = stability_score
        profile.annualized_volatility = annualized_volatility
        profile.short_return = short_return
        profile.medium_return = medium_return
        profile.long_return = long_return
        profile.current_drawdown = current_drawdown
        profile.maximum_drawdown = maximum_drawdown
        profile.regime_score = regime_score
        profile.confidence_score = confidence_score
        profile.regime_grade = grade
        profile.regime_severity = severity
        profile.transitions = transitions
        profile.regime_history = history
        profile.valid = current in self.policy.supported_regimes

        if confidence_score < self.policy.minimum_confidence_score:
            profile.warnings.append("LOW_REGIME_CONFIDENCE")
        if regime_score < self.policy.minimum_regime_score:
            profile.warnings.append("LOW_REGIME_SCORE")
        if current == "TRANSITION":
            profile.warnings.append("REGIME_TRANSITION_IN_PROGRESS")
        if severity == "CRITICAL":
            profile.warnings.append("CRITICAL_MARKET_REGIME")
            if self.policy.reject_critical_regime:
                profile.rejection_reasons.append(
                    "CRITICAL_MARKET_REGIME"
                )

        profile.allowed = not profile.rejection_reasons
        profile.metadata = {
            "policy": {
                "short_window": self.policy.short_window,
                "medium_window": self.policy.medium_window,
                "long_window": self.policy.long_window,
                "volatility_window": self.policy.volatility_window,
                "drawdown_window": self.policy.drawdown_window,
            },
            "regime_distribution": dict(Counter(history)),
            "transition_count": len(transitions),
        }
        return profile

    def _close_values(self, prices: Any) -> np.ndarray:
        if prices is None:
            return np.asarray([], dtype=float)

        if hasattr(prices, "columns"):
            for name in ("close", "Close", "adj_close", "Adj Close"):
                if name in prices.columns:
                    return np.asarray(prices[name], dtype=float).reshape(-1)

        if isinstance(prices, dict):
            for name in ("close", "Close", "adj_close", "Adj Close"):
                if name in prices:
                    return np.asarray(prices[name], dtype=float).reshape(-1)

        if isinstance(prices, Sequence) and prices:
            first = prices[0]
            if isinstance(first, dict):
                values = []
                for row in prices:
                    value = row.get("close", row.get("Close"))
                    if value is not None:
                        values.append(value)
                return np.asarray(values, dtype=float).reshape(-1)

        return np.asarray(prices, dtype=float).reshape(-1)

    def _rolling_regimes(self, close: np.ndarray) -> List[str]:
        start = max(
            self.policy.long_window,
            self.policy.volatility_window + 1,
        )
        history: List[str] = []
        for end in range(start, close.size + 1):
            subset = close[:end]
            returns = np.diff(np.log(subset))
            short_return = self._period_return(
                subset,
                self.policy.short_window,
            )
            medium_return = self._period_return(
                subset,
                self.policy.medium_window,
            )
            long_return = self._period_return(
                subset,
                self.policy.long_window,
            )
            volatility = self._annualized_volatility(returns)
            drawdown = float(self._drawdown_series(subset)[-1])
            history.append(
                self._classify(
                    short_return=short_return,
                    medium_return=medium_return,
                    long_return=long_return,
                    annualized_volatility=volatility,
                    current_drawdown=drawdown,
                )
            )
        return history

    def _classify(
        self,
        short_return: float,
        medium_return: float,
        long_return: float,
        annualized_volatility: float,
        current_drawdown: float,
    ) -> str:
        p = self.policy
        if (
            annualized_volatility >= p.stress_volatility_threshold
            or current_drawdown <= p.stress_drawdown_threshold
        ):
            return "STRESS"

        if (
            current_drawdown >= p.recovery_drawdown_threshold
            and short_return > p.momentum_threshold
            and medium_return <= 0.0
        ):
            return "RECOVERY"

        aligned_positive = (
            short_return > p.trend_threshold
            and medium_return > p.trend_threshold
            and long_return > 0.0
        )
        aligned_negative = (
            short_return < -p.trend_threshold
            and medium_return < -p.trend_threshold
            and long_return < 0.0
        )

        if aligned_positive:
            if medium_return >= p.strong_trend_threshold:
                return "STRONG_BULL_TREND"
            return "BULL_TREND"

        if aligned_negative:
            if medium_return <= -p.strong_trend_threshold:
                return "STRONG_BEAR_TREND"
            return "BEAR_TREND"

        if annualized_volatility >= p.high_volatility_threshold:
            return "HIGH_VOLATILITY"

        if (
            annualized_volatility <= p.low_volatility_threshold
            and abs(medium_return) < p.trend_threshold
        ):
            return "LOW_VOLATILITY_RANGE"

        if (
            abs(short_return) < p.trend_threshold
            and abs(medium_return) < p.strong_trend_threshold
        ):
            return "RANGE_BOUND"

        return "TRANSITION"

    def _period_return(self, close: np.ndarray, window: int) -> float:
        if close.size <= window:
            return 0.0
        return float(close[-1] / close[-window - 1] - 1.0)

    def _annualized_volatility(self, returns: np.ndarray) -> float:
        window = returns[-self.policy.volatility_window :]
        if window.size < 2:
            return 0.0
        return float(
            np.std(window, ddof=1)
            * math.sqrt(self.policy.annualization_factor)
        )

    def _drawdown_series(self, close: np.ndarray) -> np.ndarray:
        peaks = np.maximum.accumulate(close)
        return close / peaks - 1.0

    def _trend_score(self, short: float, medium: float, long: float) -> float:
        scale = max(self.policy.strong_trend_threshold, 1e-9)
        magnitude = (
            abs(short) * 0.45
            + abs(medium) * 0.35
            + abs(long) * 0.20
        )
        alignment = 1.0 if (short * medium > 0 and medium * long >= 0) else 0.55
        return self._clip(100.0 * magnitude / scale * alignment)

    def _volatility_score(self, volatility: float) -> float:
        high = max(self.policy.high_volatility_threshold, 1e-9)
        distance = abs(volatility - high) / high
        return self._clip(100.0 - 55.0 * min(distance, 1.5))

    def _momentum_score(self, short: float, medium: float) -> float:
        scale = max(self.policy.momentum_threshold, 1e-9)
        agreement = 1.0 if short * medium >= 0 else 0.45
        return self._clip(
            100.0 * min((abs(short) + abs(medium)) / (2.0 * scale), 1.0) * agreement
        )

    def _drawdown_score(self, drawdown: float) -> float:
        stress = abs(self.policy.stress_drawdown_threshold)
        return self._clip(100.0 * (1.0 - min(abs(drawdown) / stress, 1.0)))

    def _stability_score(self, history: Sequence[str]) -> float:
        if not history:
            return 0.0
        lookback = list(history[-min(30, len(history)) :])
        dominant = Counter(lookback).most_common(1)[0][1]
        transitions = sum(
            1 for left, right in zip(lookback, lookback[1:]) if left != right
        )
        dominance = dominant / len(lookback)
        transition_penalty = transitions / max(len(lookback) - 1, 1)
        return self._clip(100.0 * (0.75 * dominance + 0.25 * (1.0 - transition_penalty)))

    def _confidence_score(self, **values: float | str) -> float:
        current = str(values.pop("current_regime"))
        weights = {
            "trend_score": 0.25,
            "volatility_score": 0.15,
            "momentum_score": 0.20,
            "drawdown_score": 0.15,
            "stability_score": 0.25,
        }
        score = sum(float(values[name]) * weight for name, weight in weights.items())
        if current in {"TRANSITION", "UNKNOWN"}:
            score *= 0.75
        return self._clip(score)

    def _regime_score(self, confidence: float, stability: float, regime: str) -> float:
        score = 0.65 * confidence + 0.35 * stability
        if regime == "STRESS":
            score *= 0.75
        return self._clip(score)

    def _severity(self, regime: str, volatility: float, drawdown: float) -> str:
        if regime == "STRESS" and (
            volatility >= self.policy.stress_volatility_threshold * 1.25
            or drawdown <= self.policy.stress_drawdown_threshold * 1.5
        ):
            return "CRITICAL"
        if regime == "STRESS":
            return "SEVERE"
        if regime in {"HIGH_VOLATILITY", "STRONG_BEAR_TREND"}:
            return "MODERATE"
        return "LOW"

    def _grade(self, score: float) -> str:
        if score >= 85.0:
            return "A"
        if score >= 75.0:
            return "B"
        if score >= 65.0:
            return "C"
        if score >= 50.0:
            return "D"
        return "F"

    def _previous_distinct(self, history: Sequence[str], current: str) -> str:
        for regime in reversed(history[:-1]):
            if regime != current:
                return regime
        return "UNKNOWN"

    def _duration(self, history: Sequence[str], current: str) -> int:
        count = 0
        for regime in reversed(history):
            if regime != current:
                break
            count += 1
        return count

    def _transitions(self, history: Sequence[str]) -> List[MarketRegimeTransition]:
        transitions: List[MarketRegimeTransition] = []
        for index, (left, right) in enumerate(zip(history, history[1:]), start=1):
            if left != right:
                transitions.append(
                    MarketRegimeTransition(
                        from_regime=left,
                        to_regime=right,
                        observation_index=index,
                        confidence=0.0,
                    )
                )
        return transitions

    def _clip(self, value: float) -> float:
        return float(max(0.0, min(100.0, value)))
