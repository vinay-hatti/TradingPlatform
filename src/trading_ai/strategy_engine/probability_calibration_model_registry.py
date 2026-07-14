from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from trading_ai.strategy_engine.probability_calibration_profile import (
    CalibrationBin, CalibrationModel, ProbabilityCalibrationProfile,
)
from trading_ai.strategy_engine.segmented_probability_calibration_profile import (
    SegmentCalibrationResult, SegmentedProbabilityCalibrationProfile,
)
from trading_ai.strategy_engine.probability_calibration_serialization import probability_calibration_to_dict


@dataclass
class CalibrationRegistryEntry:
    version: str
    created_at: str
    profile: SegmentedProbabilityCalibrationProfile
    active: bool = True
    metadata: dict = field(default_factory=dict)


class ProbabilityCalibrationModelRegistry:
    """Small JSON-backed registry; no database or new dependency required."""
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.entries: dict[str, CalibrationRegistryEntry] = {}
        if self.path and self.path.exists():
            self.load()

    def register(self, profile, version: str | None = None, *, activate=True, metadata=None):
        version = version or self._next_version()
        if version in self.entries:
            raise ValueError(f"calibration model version already exists: {version}")
        if activate:
            for item in self.entries.values():
                item.active = False
        entry = CalibrationRegistryEntry(
            version=version,
            created_at=datetime.now(timezone.utc).isoformat(),
            profile=profile, active=activate, metadata=dict(metadata or {}),
        )
        self.entries[version] = entry
        if self.path:
            self.save()
        return entry

    def active(self):
        active = [x for x in self.entries.values() if x.active]
        return sorted(active, key=lambda x: x.created_at)[-1] if active else None

    def activate(self, version):
        if version not in self.entries:
            raise KeyError(version)
        for key, item in self.entries.items():
            item.active = key == version
        if self.path:
            self.save()
        return self.entries[version]

    def get(self, version):
        return self.entries.get(version)

    def list_versions(self):
        return sorted(self.entries)

    def champion(self):
        return self.active()

    def challengers(self):
        return [entry for entry in self.entries.values() if not entry.active]

    def promote(self, version, governance_profile=None):
        entry = self.activate(version)
        if governance_profile is not None:
            entry.metadata["last_governance_recommendation"] = getattr(governance_profile, "recommendation", "UNKNOWN")
            entry.metadata["governance_confidence_score"] = getattr(governance_profile, "confidence_score", 0.0)
            entry.metadata["promoted_by_governance"] = True
            if self.path:
                self.save()
        return entry

    def save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"entries": [
            {"version": e.version, "created_at": e.created_at, "active": e.active,
             "metadata": e.metadata, "profile": probability_calibration_to_dict(e.profile)}
            for e in self.entries.values()
        ]}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def load(self):
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.entries = {}
        for raw in payload.get("entries", []):
            profile = self._segmented_profile(raw["profile"])
            self.entries[raw["version"]] = CalibrationRegistryEntry(
                version=raw["version"], created_at=raw["created_at"],
                active=bool(raw.get("active")), metadata=raw.get("metadata", {}), profile=profile,
            )
        return self

    def _next_version(self):
        numbers = []
        for version in self.entries:
            if version.startswith("v") and version[1:].isdigit():
                numbers.append(int(version[1:]))
        return f"v{max(numbers, default=0) + 1}"

    @classmethod
    def _segmented_profile(cls, data):
        global_profile = cls._profile(data.get("global_profile")) if data.get("global_profile") else None
        segments = {}
        for key, raw in data.get("segment_profiles", {}).items():
            segments[key] = SegmentCalibrationResult(
                segment_key=raw["segment_key"], dimensions=raw.get("dimensions", {}),
                observation_count=raw.get("observation_count", 0),
                profile=cls._profile(raw["profile"]), priority=raw.get("priority", 0),
            )
        kwargs = {k: v for k, v in data.items() if k not in {"global_profile", "segment_profiles"}}
        return SegmentedProbabilityCalibrationProfile(global_profile=global_profile, segment_profiles=segments, **kwargs)

    @staticmethod
    def _profile(data):
        model_raw = data["model"]
        model = CalibrationModel(**model_raw)
        raw_bins = [CalibrationBin(**x) for x in data.get("raw_reliability_bins", [])]
        calibrated_bins = [CalibrationBin(**x) for x in data.get("calibrated_reliability_bins", [])]
        kwargs = {k: v for k, v in data.items() if k not in {"model", "raw_reliability_bins", "calibrated_reliability_bins"}}
        return ProbabilityCalibrationProfile(model=model, raw_reliability_bins=raw_bins,
                                             calibrated_reliability_bins=calibrated_bins, **kwargs)
