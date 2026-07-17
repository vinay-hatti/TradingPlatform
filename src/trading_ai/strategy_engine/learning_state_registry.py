from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .online_adaptation_policy import OnlineAdaptationPolicy
from .online_adaptation_profile import LearningStatePromotionProfile, LearningStateRegistryProfile, LearningStateVersionProfile
from .online_adaptation_serialization import online_adaptation_to_dict


class LearningStateRegistry:
    def __init__(self, path: str | Path | None = None, policy: OnlineAdaptationPolicy | None = None):
        self.path = Path(path) if path else None
        self.policy = policy or OnlineAdaptationPolicy()
        self._versions: list[LearningStateVersionProfile] = []
        self.active_version: str | None = None
        self.champion_version: str | None = None
        self.challenger_version: str | None = None
        if self.path and self.path.exists():
            self.load()

    def register(self, version: str, weights: dict[str, float], adaptation_score: float, status: str = "CANDIDATE", source_version: str | None = None, actor: str = "system", reason: str = "", metadata: dict[str, Any] | None = None) -> LearningStateVersionProfile:
        if any(v.version == version for v in self._versions):
            raise ValueError(f"Learning-state version already exists: {version}")
        profile = LearningStateVersionProfile(version, datetime.now(timezone.utc), status.upper(), self._normalize(weights), float(adaptation_score), source_version, actor, reason, metadata or {})
        self._versions.append(profile)
        if profile.status == "CHAMPION": self.champion_version = version
        if profile.status == "CHALLENGER": self.challenger_version = version
        if profile.status in {"ACTIVE", "CHAMPION"}: self.active_version = version
        self.save()
        return profile

    def evaluate_promotion(self, challenger_version: str | None = None) -> LearningStatePromotionProfile:
        challenger_version = challenger_version or self.challenger_version
        champion = self.get(self.champion_version) if self.champion_version else None
        challenger = self.get(challenger_version) if challenger_version else None
        rejections = []
        if challenger is None: rejections.append("Challenger learning state is unavailable.")
        if champion is None: rejections.append("Champion learning state is unavailable.")
        champion_score = champion.adaptation_score if champion else 0.0
        challenger_score = challenger.adaptation_score if challenger else 0.0
        improvement = challenger_score - champion_score
        if challenger and challenger_score < self.policy.minimum_promotion_score:
            rejections.append("Challenger score is below the minimum promotion score.")
        if champion and challenger and improvement < self.policy.minimum_champion_improvement:
            rejections.append("Challenger improvement is below the promotion threshold.")
        allowed = not rejections
        promotion_score = max(0.0, min(100.0, challenger_score + max(improvement, 0.0)))
        return LearningStatePromotionProfile(bool(challenger and champion), allowed, self.champion_version, challenger_version, champion_score, challenger_score, improvement, promotion_score, "PROMOTE_CHALLENGER" if allowed else "RETAIN_CHAMPION", "A" if allowed else "F", "LOW" if allowed else "SEVERE", rejection_reasons=tuple(rejections))

    def promote(self, challenger_version: str | None = None, actor: str = "system", reason: str = "controlled promotion") -> LearningStatePromotionProfile:
        decision = self.evaluate_promotion(challenger_version)
        if not decision.allowed:
            return decision
        challenger_version = decision.challenger_version
        updated=[]
        for v in self._versions:
            if v.version == self.champion_version: updated.append(replace(v, status="SUPERSEDED"))
            elif v.version == challenger_version: updated.append(replace(v, status="CHAMPION", actor=actor, reason=reason))
            else: updated.append(v)
        self._versions=updated
        self.champion_version=challenger_version
        self.active_version=challenger_version
        if self.challenger_version == challenger_version: self.challenger_version=None
        self.save()
        return decision

    def rollback(self, version: str, actor: str = "system", reason: str = "rollback") -> LearningStateVersionProfile:
        target=self.get(version)
        if target is None: raise KeyError(version)
        self.active_version=version
        self._versions=[replace(v, status=("ACTIVE" if v.version==version else v.status), actor=(actor if v.version==version else v.actor), reason=(reason if v.version==version else v.reason)) for v in self._versions]
        self.save(); return self.get(version)

    def get(self, version: str | None) -> LearningStateVersionProfile | None:
        return next((v for v in self._versions if v.version == version), None)

    def profile(self) -> LearningStateRegistryProfile:
        return LearningStateRegistryProfile(True, self.policy.registry_schema_version, self.active_version, self.champion_version, self.challenger_version, tuple(self._versions))

    def save(self) -> None:
        if not self.path: return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(online_adaptation_to_dict(self.profile()), indent=2, sort_keys=True), encoding="utf-8")

    def load(self) -> None:
        data=json.loads(self.path.read_text(encoding="utf-8")); self.active_version=data.get("active_version"); self.champion_version=data.get("champion_version"); self.challenger_version=data.get("challenger_version")
        self._versions=[LearningStateVersionProfile(v["version"], datetime.fromisoformat(v["created_at"]), v["status"], {str(k):float(x) for k,x in v.get("weights",{}).items()}, float(v.get("adaptation_score",0.0)), v.get("source_version"), v.get("actor","system"), v.get("reason",""), v.get("metadata",{})) for v in data.get("versions",[])]

    @staticmethod
    def _normalize(weights: dict[str,float]) -> dict[str,float]:
        clean={str(k).upper():max(float(v),0.0) for k,v in weights.items()}; total=sum(clean.values()); return {k:v/total for k,v in clean.items()} if total>0 else clean
