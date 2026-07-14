from __future__ import annotations

import math
from collections import Counter
from typing import Iterable

from .market_regime_drift_policy import MarketRegimeDriftPolicy
from .market_regime_drift_profile import MarketRegimeDriftProfile


class MarketRegimeDriftEngine:
    def __init__(self, policy: MarketRegimeDriftPolicy | None = None):
        self.policy = policy or MarketRegimeDriftPolicy()

    @staticmethod
    def _value(item, name, default=None):
        if isinstance(item, dict):
            return item.get(name, default)
        return getattr(item, name, default)

    def _distribution(self, items: list[object]) -> dict[str, float]:
        counts = Counter(str(self._value(x, "current_regime", self._value(x, "regime", "UNKNOWN")) or "UNKNOWN").upper() for x in items)
        total = sum(counts.values()) or 1
        return {key: value / total for key, value in sorted(counts.items())}

    @staticmethod
    def _mean(items: list[object], name: str) -> float:
        vals = []
        for item in items:
            try:
                value = item.get(name) if isinstance(item, dict) else getattr(item, name, None)
                if value is not None:
                    vals.append(float(value))
            except Exception:
                pass
        return sum(vals) / len(vals) if vals else 0.0

    @staticmethod
    def _transition_rate(items: list[object]) -> float:
        flags = []
        for item in items:
            value = item.get("transition_detected", False) if isinstance(item, dict) else getattr(item, "transition_detected", False)
            flags.append(1.0 if bool(value) else 0.0)
        return sum(flags) / len(flags) if flags else 0.0

    @staticmethod
    def _psi(reference: dict[str, float], recent: dict[str, float]) -> float:
        eps = 1e-6
        keys = set(reference) | set(recent)
        return sum((recent.get(k, eps) - reference.get(k, eps)) * math.log(recent.get(k, eps) / reference.get(k, eps)) for k in keys)

    def analyze(self, reference_profiles: Iterable[object], recent_profiles: Iterable[object]) -> MarketRegimeDriftProfile:
        reference = list(reference_profiles or [])
        recent = list(recent_profiles or [])
        p = self.policy
        rejections: list[str] = []
        warnings: list[str] = []
        if len(reference) < p.minimum_reference_observations:
            rejections.append("INSUFFICIENT_REFERENCE_REGIME_OBSERVATIONS")
        if len(recent) < p.minimum_recent_observations:
            rejections.append("INSUFFICIENT_RECENT_REGIME_OBSERVATIONS")
        if rejections:
            return MarketRegimeDriftProfile(
                valid=False,
                allowed=False,
                reference_observation_count=len(reference),
                recent_observation_count=len(recent),
                rejection_reasons=rejections,
            )

        ref_dist = self._distribution(reference)
        recent_dist = self._distribution(recent)
        psi = self._psi(ref_dist, recent_dist)
        score_shift = self._mean(recent, "regime_score") - self._mean(reference, "regime_score")
        confidence_shift = self._mean(recent, "confidence_score") - self._mean(reference, "confidence_score")
        transition_shift = self._transition_rate(recent) - self._transition_rate(reference)

        if psi >= p.warning_psi:
            warnings.append("REGIME_POPULATION_DRIFT")
        if abs(score_shift) >= p.warning_score_shift:
            warnings.append("REGIME_SCORE_DRIFT")
        if abs(transition_shift) >= p.warning_transition_rate_shift:
            warnings.append("REGIME_TRANSITION_RATE_DRIFT")

        severity = "LOW"
        if psi >= p.critical_psi:
            severity = "CRITICAL"
        elif psi >= p.severe_psi or abs(score_shift) >= p.severe_score_shift or abs(transition_shift) >= p.severe_transition_rate_shift:
            severity = "SEVERE"
        elif warnings:
            severity = "MODERATE"

        penalty = min(100.0, psi * 100.0 + abs(score_shift) * 0.8 + abs(confidence_shift) * 0.4 + abs(transition_shift) * 80.0)
        drift_score = max(0.0, 100.0 - penalty)
        grade = "A" if drift_score >= 85 else "B" if drift_score >= 75 else "C" if drift_score >= 65 else "D" if drift_score >= 50 else "F"
        allowed = drift_score >= p.minimum_drift_score and not (p.reject_critical_drift and severity == "CRITICAL")
        if not allowed:
            rejections.append("MARKET_REGIME_DRIFT_NOT_ALLOWED")

        return MarketRegimeDriftProfile(
            valid=True,
            allowed=allowed,
            reference_observation_count=len(reference),
            recent_observation_count=len(recent),
            regime_population_stability_index=psi,
            regime_score_shift=score_shift,
            confidence_shift=confidence_shift,
            transition_rate_shift=transition_shift,
            reference_regime_distribution=ref_dist,
            recent_regime_distribution=recent_dist,
            drift_score=drift_score,
            drift_grade=grade,
            drift_severity=severity,
            warnings=warnings,
            rejection_reasons=rejections,
        )
