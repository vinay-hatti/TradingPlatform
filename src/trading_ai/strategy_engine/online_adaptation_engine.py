from __future__ import annotations

import math
from typing import Any, Iterable

from .online_adaptation_policy import OnlineAdaptationPolicy
from .online_adaptation_profile import OnlineAdaptationProfile, StrategyWeightUpdateProfile


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _grade(score: float) -> str:
    if score >= 90.0: return "A+"
    if score >= 80.0: return "A"
    if score >= 70.0: return "B"
    if score >= 60.0: return "C"
    if score >= 50.0: return "D"
    return "F"


def _severity(score: float, allowed: bool) -> str:
    if allowed and score >= 75.0: return "LOW"
    if allowed: return "MODERATE"
    if score >= 45.0: return "SEVERE"
    return "CRITICAL"


class OnlineAdaptationEngine:
    def __init__(self, policy: OnlineAdaptationPolicy | None = None):
        self.policy = policy or OnlineAdaptationPolicy()

    def adapt(self, current_weights: dict[str, float], learning_profiles: Iterable[Any]) -> OnlineAdaptationProfile:
        current = self._normalize(current_weights)
        profiles = {str(_value(p, "strategy", "")).upper(): p for p in learning_profiles if _value(p, "strategy", None)}
        strategies = sorted(set(current) | set(profiles))
        if not strategies:
            return OnlineAdaptationProfile(False, False, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "F", "CRITICAL", "NO_STRATEGY_STATE", rejection_reasons=("No strategy weights or learning profiles were supplied.",))

        raw_targets: dict[str, float] = {}
        diagnostics: dict[str, tuple[float, float, float, int, bool]] = {}
        components = self.policy.normalized_update_components()
        for strategy in strategies:
            p = profiles.get(strategy)
            perf = float(_value(p, "performance_score", 50.0))
            conf = float(_value(p, "confidence_score", 0.0))
            stability = float(_value(p, "stability_score", 50.0))
            obs = int(_value(p, "observation_count", 0))
            profile_allowed = bool(_value(p, "allowed", True))
            update_score = components["performance"] * perf + components["confidence"] * conf + components["stability"] * stability
            raw_targets[strategy] = max(update_score, 0.0)
            diagnostics[strategy] = (perf, conf, stability, obs, profile_allowed)

        targets = self._normalize(raw_targets)
        updates: list[StrategyWeightUpdateProfile] = []
        proposed: dict[str, float] = {}
        any_rejected = False
        for strategy in strategies:
            cur = current.get(strategy, 0.0)
            target = targets.get(strategy, 0.0)
            perf, conf, stability, obs, profile_allowed = diagnostics[strategy]
            warnings: list[str] = []
            rejections: list[str] = []
            valid = strategy in profiles
            if not valid:
                warnings.append("Learning profile unavailable; current weight retained.")
            if obs < self.policy.minimum_observations_per_update:
                rejections.append(f"Observation count {obs} is below {self.policy.minimum_observations_per_update}.")
            if conf < self.policy.minimum_confidence_score:
                rejections.append(f"Confidence score {conf:.2f} is below {self.policy.minimum_confidence_score:.2f}.")
            if not profile_allowed:
                rejections.append("Learning profile is not governance-approved.")
            allowed = valid and not rejections
            desired = cur + self.policy.learning_rate * (target - cur) if allowed else cur
            absolute_cap = self.policy.maximum_absolute_weight_change
            relative_cap = abs(cur) * self.policy.maximum_relative_weight_change if cur > 0.0 else absolute_cap
            cap = min(absolute_cap, max(relative_cap, self.policy.minimum_strategy_weight))
            delta = _clip(desired - cur, -cap, cap)
            proposed_weight = _clip(cur + delta, self.policy.minimum_strategy_weight if allowed else 0.0, self.policy.maximum_strategy_weight)
            proposed[strategy] = proposed_weight
            any_rejected = any_rejected or bool(rejections)
            updates.append(StrategyWeightUpdateProfile(
                strategy=strategy, valid=valid, allowed=allowed, current_weight=cur, target_weight=target,
                proposed_weight=proposed_weight, applied_weight=proposed_weight, absolute_change=abs(proposed_weight-cur),
                relative_change=(abs(proposed_weight-cur)/cur if cur > 0 else abs(proposed_weight-cur)), performance_score=perf,
                confidence_score=conf, stability_score=stability, update_score=components["performance"]*perf + components["confidence"]*conf + components["stability"]*stability,
                observation_count=obs, grade=_grade((perf+conf+stability)/3.0), severity="LOW" if allowed else "SEVERE",
                warnings=tuple(warnings), rejection_reasons=tuple(rejections), metadata={"learning_rate": self.policy.learning_rate},
            ))

        normalized = self._normalize(proposed)
        finalized = []
        for u in updates:
            applied = normalized.get(u.strategy, u.current_weight)
            finalized.append(StrategyWeightUpdateProfile(**{**u.__dict__, "applied_weight": applied, "absolute_change": abs(applied-u.current_weight), "relative_change": (abs(applied-u.current_weight)/u.current_weight if u.current_weight > 0 else abs(applied-u.current_weight))}))
        before_conc = sum(w*w for w in current.values())
        after_conc = sum(w*w for w in normalized.values())
        before_eff = 1.0 / before_conc if before_conc > 0 else 0.0
        after_eff = 1.0 / after_conc if after_conc > 0 else 0.0
        applied_count = sum(1 for u in finalized if u.allowed and u.absolute_change > 1e-12)
        total_change = sum(u.absolute_change for u in finalized)
        max_change = max((u.absolute_change for u in finalized), default=0.0)
        allowed = applied_count > 0 and (not self.policy.require_all_strategies_allowed or not any_rejected)
        score = sum(u.update_score * u.applied_weight for u in finalized)
        recommendation = "APPLY_CONTROLLED_UPDATE" if allowed else "RETAIN_CURRENT_STATE"
        warnings = tuple(r for u in finalized for r in u.warnings)
        rejections = tuple(r for u in finalized for r in u.rejection_reasons)
        return OnlineAdaptationProfile(True, allowed, len(finalized), applied_count, total_change, max_change, before_conc, after_conc, before_eff, after_eff, score, _grade(score), _severity(score, allowed), recommendation, tuple(finalized), warnings, rejections, {"weights_before": current, "weights_after": normalized})

    @staticmethod
    def _normalize(weights: dict[str, float]) -> dict[str, float]:
        clean = {str(k).upper(): max(float(v), 0.0) for k, v in (weights or {}).items()}
        total = sum(clean.values())
        if total <= 0.0:
            return {k: 1.0/len(clean) for k in clean} if clean else {}
        return {k: v/total for k, v in clean.items()}
