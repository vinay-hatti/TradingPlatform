from __future__ import annotations

import math
from collections import Counter
from typing import Iterable, List, Sequence

import numpy as np

from trading_ai.strategy_engine.market_regime_forecast_policy import (
    MarketRegimeForecastPolicy,
)
from trading_ai.strategy_engine.market_regime_forecast_profile import (
    MarketRegimeForecastProfile,
    MarketRegimeHorizonForecast,
    MarketRegimeTransitionProbability,
)
from trading_ai.strategy_engine.market_regime_profile import MarketRegimeProfile


class MarketRegimeForecastEngine:
    """First-order Markov regime forecast with institutional diagnostics."""

    def __init__(self, policy: MarketRegimeForecastPolicy | None = None):
        self.policy = policy or MarketRegimeForecastPolicy()

    def forecast_profile(
        self,
        regime_profile: MarketRegimeProfile,
    ) -> MarketRegimeForecastProfile:
        return self.forecast(
            regime_history=regime_profile.regime_history,
            symbol=regime_profile.symbol,
            current_regime_duration=regime_profile.regime_duration,
            source_profile=regime_profile,
        )

    def forecast(
        self,
        regime_history: Sequence[str] | Iterable[str],
        symbol: str = "UNKNOWN",
        current_regime_duration: int | None = None,
        source_profile: MarketRegimeProfile | None = None,
    ) -> MarketRegimeForecastProfile:
        history = [str(item or "UNKNOWN") for item in regime_history]
        history = history[-self.policy.recent_transition_lookback :]
        profile = MarketRegimeForecastProfile(
            symbol=str(symbol or "UNKNOWN"),
            history_observation_count=len(history),
        )

        if len(history) < self.policy.minimum_history_observations:
            return self._invalid(profile, "INSUFFICIENT_REGIME_HISTORY")

        states = sorted(set(history))
        if not states:
            return self._invalid(profile, "EMPTY_REGIME_HISTORY")

        index = {state: position for position, state in enumerate(states)}
        counts = np.zeros((len(states), len(states)), dtype=float)
        raw_counts = Counter()
        for left, right in zip(history, history[1:]):
            counts[index[left], index[right]] += 1.0
            raw_counts[(left, right)] += 1

        transition_count = len(history) - 1
        profile.transition_count = transition_count
        profile.state_count = len(states)
        profile.current_regime = history[-1]
        profile.current_regime_duration = (
            int(current_regime_duration)
            if current_regime_duration is not None
            else self._duration(history, history[-1])
        )

        if transition_count < self.policy.minimum_transition_count:
            return self._invalid(profile, "INSUFFICIENT_REGIME_TRANSITIONS")

        smoothed = counts + float(self.policy.laplace_smoothing)
        row_sums = smoothed.sum(axis=1, keepdims=True)
        matrix = np.divide(
            smoothed,
            row_sums,
            out=np.zeros_like(smoothed),
            where=row_sums > 0.0,
        )

        current_index = index[profile.current_regime]
        next_vector = matrix[current_index]
        profile.next_regime_probabilities = {
            state: float(next_vector[index[state]]) for state in states
        }
        forecast_index = int(np.argmax(next_vector))
        profile.forecast_regime = states[forecast_index]
        profile.forecast_probability = float(next_vector[forecast_index])
        profile.persistence_probability = float(next_vector[current_index])
        profile.transition_probability = 1.0 - profile.persistence_probability
        profile.expected_remaining_duration = self._expected_remaining_duration(
            profile.persistence_probability
        )
        profile.transition_entropy = self._normalized_entropy(next_vector)
        profile.persistence_score = self._clip(
            100.0 * profile.persistence_probability
        )
        profile.forecast_confidence_score = self._clip(
            100.0 * profile.forecast_probability * (1.0 - 0.55 * profile.transition_entropy)
        )
        profile.forecast_score = self._clip(
            0.55 * profile.forecast_confidence_score
            + 0.30 * profile.persistence_score
            + 0.15 * min(100.0, transition_count)
        )
        profile.forecast_grade = self._grade(profile.forecast_score)
        profile.forecast_severity = self._severity(profile)

        for from_state in states:
            for to_state in states:
                profile.transition_probabilities.append(
                    MarketRegimeTransitionProbability(
                        from_regime=from_state,
                        to_regime=to_state,
                        transition_count=int(raw_counts[(from_state, to_state)]),
                        probability=float(matrix[index[from_state], index[to_state]]),
                    )
                )

        vector = np.zeros(len(states), dtype=float)
        vector[current_index] = 1.0
        for horizon in range(1, self.policy.forecast_horizon + 1):
            vector = vector @ matrix
            best = int(np.argmax(vector))
            profile.horizon_forecasts.append(
                MarketRegimeHorizonForecast(
                    horizon=horizon,
                    most_likely_regime=states[best],
                    probability=float(vector[best]),
                    regime_probabilities={
                        state: float(vector[index[state]]) for state in states
                    },
                )
            )

        if profile.persistence_probability < self.policy.persistence_warning_threshold:
            profile.warnings.append("LOW_REGIME_PERSISTENCE")
        if profile.transition_probability >= self.policy.transition_warning_threshold:
            profile.warnings.append("ELEVATED_REGIME_TRANSITION_RISK")
        if profile.forecast_confidence_score < self.policy.minimum_forecast_confidence:
            profile.warnings.append("LOW_REGIME_FORECAST_CONFIDENCE")
        if profile.forecast_score < self.policy.minimum_forecast_score:
            profile.warnings.append("LOW_REGIME_FORECAST_SCORE")
        if profile.forecast_severity == "CRITICAL":
            profile.warnings.append("CRITICAL_REGIME_FORECAST")
            if self.policy.reject_critical_forecast:
                profile.rejection_reasons.append("CRITICAL_REGIME_FORECAST")

        profile.valid = True
        profile.allowed = not profile.rejection_reasons
        profile.metadata = {
            "states": states,
            "transition_matrix": matrix.tolist(),
            "laplace_smoothing": self.policy.laplace_smoothing,
            "forecast_horizon": self.policy.forecast_horizon,
            "source_regime_score": getattr(source_profile, "regime_score", None),
            "source_regime_confidence": getattr(
                source_profile, "confidence_score", None
            ),
        }
        return profile

    def _invalid(
        self,
        profile: MarketRegimeForecastProfile,
        reason: str,
    ) -> MarketRegimeForecastProfile:
        profile.valid = False
        profile.allowed = not self.policy.reject_invalid_profile
        profile.forecast_severity = "MODERATE"
        profile.warnings.append(reason)
        if self.policy.reject_invalid_profile:
            profile.rejection_reasons.append(reason)
        return profile

    def _duration(self, history: Sequence[str], current: str) -> int:
        count = 0
        for regime in reversed(history):
            if regime != current:
                break
            count += 1
        return count

    def _expected_remaining_duration(self, persistence: float) -> float:
        if persistence >= 0.999999:
            return float("inf")
        return float(persistence / max(1.0 - persistence, 1e-12))

    def _normalized_entropy(self, probabilities: np.ndarray) -> float:
        positive = probabilities[probabilities > 0.0]
        if positive.size <= 1:
            return 0.0
        entropy = -float(np.sum(positive * np.log(positive)))
        maximum = math.log(float(probabilities.size))
        return float(entropy / maximum) if maximum > 0.0 else 0.0

    def _severity(self, profile: MarketRegimeForecastProfile) -> str:
        if (
            profile.forecast_regime == "STRESS"
            and profile.forecast_probability >= 0.60
        ):
            return "CRITICAL"
        if (
            profile.forecast_regime in {"STRESS", "STRONG_BEAR_TREND"}
            or profile.transition_probability >= 0.70
        ):
            return "SEVERE"
        if (
            profile.forecast_regime in {"BEAR_TREND", "HIGH_VOLATILITY", "TRANSITION"}
            or profile.transition_probability >= 0.50
        ):
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

    def _clip(self, value: float) -> float:
        return float(max(0.0, min(100.0, value)))
