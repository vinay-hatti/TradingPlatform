from __future__ import annotations

from collections import defaultdict
from math import sqrt
from typing import Any, Mapping, Sequence

from trading_ai.strategy_engine.market_breadth_policy import MarketBreadthPolicy
from trading_ai.strategy_engine.market_breadth_profile import (
    MarketBreadthContribution,
    MarketBreadthProfile,
)


class MarketBreadthEngine:
    def __init__(self, policy: MarketBreadthPolicy | None = None):
        self.policy = policy or MarketBreadthPolicy()

    @staticmethod
    def _value(obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90: return "A+"
        if score >= 80: return "A"
        if score >= 70: return "B"
        if score >= 60: return "C"
        if score >= 50: return "D"
        return "F"

    def analyze(
        self,
        regime_profiles: Mapping[str, Any] | Sequence[Any],
        weights: Mapping[str, float] | Sequence[float] | None = None,
    ) -> MarketBreadthProfile:
        if isinstance(regime_profiles, Mapping):
            items = list(regime_profiles.items())
        else:
            items = [
                (str(self._value(profile, "symbol", f"SYMBOL_{i+1}")), profile)
                for i, profile in enumerate(regime_profiles)
            ]

        valid_items = [(s, p) for s, p in items if bool(self._value(p, "valid", False))]
        if len(valid_items) < self.policy.minimum_symbols:
            return MarketBreadthProfile(
                symbol_count=len(valid_items), valid=False,
                allowed=not self.policy.reject_invalid_profile,
                warnings=["INSUFFICIENT_VALID_REGIME_PROFILES"],
                rejection_reasons=(
                    ["INSUFFICIENT_VALID_REGIME_PROFILES"]
                    if self.policy.reject_invalid_profile else []
                ),
            )

        raw_weights = []
        for index, (symbol, _) in enumerate(valid_items):
            if isinstance(weights, Mapping):
                raw = float(weights.get(symbol, 1.0))
            elif weights is not None and index < len(weights):
                raw = float(weights[index])
            else:
                raw = 1.0
            raw_weights.append(max(raw, 0.0))
        total = sum(raw_weights) or float(len(raw_weights))
        normalized = [w / total for w in raw_weights]

        regime_weights = defaultdict(float)
        contributions = []
        scores, confidences = [], []
        bullish = bearish = stressed = 0.0
        for (symbol, profile), weight in zip(valid_items, normalized):
            regime = str(self._value(profile, "current_regime", "UNKNOWN")).upper()
            score = float(self._value(profile, "regime_score", 0.0) or 0.0)
            confidence = float(self._value(profile, "confidence_score", 0.0) or 0.0)
            is_bull = regime in self.policy.bullish_regimes
            is_bear = regime in self.policy.bearish_regimes
            is_stress = regime in self.policy.stressed_regimes
            bullish += weight if is_bull else 0.0
            bearish += weight if is_bear else 0.0
            stressed += weight if is_stress else 0.0
            regime_weights[regime] += weight
            scores.append((score, weight)); confidences.append((confidence, weight))
            contributions.append(MarketBreadthContribution(
                symbol=symbol, regime=regime, weight=weight,
                bullish=is_bull, bearish=is_bear, stressed=is_stress,
                confidence_score=confidence, regime_score=score,
            ))

        neutral = max(0.0, 1.0 - bullish - bearish)
        dominant_regime, dominant_weight = max(regime_weights.items(), key=lambda x: x[1])
        regime_dispersion = max(0.0, 1.0 - sum(v * v for v in regime_weights.values()))
        mean_score = sum(v*w for v,w in scores)
        mean_conf = sum(v*w for v,w in confidences)
        score_dispersion = sqrt(sum(w*(v-mean_score)**2 for v,w in scores)) / 100.0
        confidence_dispersion = sqrt(sum(w*(v-mean_conf)**2 for v,w in confidences)) / 100.0
        concentration = max(normalized)
        effective_count = 1.0 / sum(w*w for w in normalized)
        agreement = dominant_weight * 100.0

        if stressed >= self.policy.critical_stress_breadth:
            portfolio_regime = "STRESS"
        elif bullish >= self.policy.minimum_bullish_breadth:
            portfolio_regime = "BULL_TREND"
        elif bearish >= self.policy.severe_bearish_breadth:
            portfolio_regime = "BEAR_TREND"
        elif regime_dispersion >= self.policy.maximum_dispersion:
            portfolio_regime = "TRANSITION"
        else:
            portfolio_regime = dominant_regime

        score = 100.0
        score -= regime_dispersion * 35.0
        score -= score_dispersion * 20.0
        score -= confidence_dispersion * 15.0
        score -= max(0.0, concentration - 0.25) * 40.0
        score -= stressed * 35.0
        score = max(0.0, min(100.0, score))

        if stressed >= self.policy.critical_stress_breadth:
            severity = "CRITICAL"
        elif bearish >= self.policy.severe_bearish_breadth:
            severity = "SEVERE"
        elif regime_dispersion >= self.policy.maximum_dispersion:
            severity = "MODERATE"
        else:
            severity = "LOW"

        warnings = []
        rejections = []
        if regime_dispersion >= self.policy.maximum_dispersion:
            warnings.append("ELEVATED_MARKET_REGIME_DISPERSION")
        if concentration >= self.policy.maximum_concentration:
            warnings.append("MARKET_BREADTH_CONCENTRATION")
        if score < self.policy.minimum_breadth_score:
            warnings.append("LOW_MARKET_BREADTH_SCORE")
        if severity == "CRITICAL" and self.policy.reject_critical_market_state:
            rejections.append("CRITICAL_MARKET_BREADTH_STATE")
        allowed = not rejections

        return MarketBreadthProfile(
            symbol_count=len(valid_items), total_weight=sum(normalized),
            dominant_regime=dominant_regime, portfolio_regime=portfolio_regime,
            bullish_breadth=bullish, bearish_breadth=bearish,
            neutral_breadth=neutral, stress_breadth=stressed,
            regime_dispersion=regime_dispersion,
            score_dispersion=score_dispersion,
            confidence_dispersion=confidence_dispersion,
            concentration_score=concentration,
            effective_symbol_count=effective_count,
            agreement_score=agreement,
            breadth_score=score,
            breadth_grade=self._grade(score),
            breadth_severity=severity,
            allowed=allowed, valid=True,
            regime_weights=dict(sorted(regime_weights.items())),
            contributions=contributions,
            warnings=warnings, rejection_reasons=rejections,
            metadata={"mean_regime_score": mean_score, "mean_confidence_score": mean_conf},
        )
