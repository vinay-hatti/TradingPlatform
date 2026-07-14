from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MarketRegimeModelRegistry:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._versions: dict[str, dict[str, Any]] = {}
        self._active_version: str | None = None
        if self.path and self.path.exists():
            self.load()

    def register(self, version: str, model_config: dict[str, Any], metrics: dict[str, Any] | None = None, activate: bool = False):
        self._versions[str(version)] = {
            "version": str(version),
            "model_config": dict(model_config or {}),
            "metrics": dict(metrics or {}),
            "active": False,
        }
        if activate or self._active_version is None:
            self.activate(str(version))
        self.save()
        return self._versions[str(version)]

    def activate(self, version: str):
        if version not in self._versions:
            raise KeyError(f"Unknown market-regime model version: {version}")
        for item in self._versions.values():
            item["active"] = False
        self._versions[version]["active"] = True
        self._active_version = version
        self.save()
        return self._versions[version]

    def promote(self, version: str, governance_profile=None):
        item = self.activate(version)
        item["governance"] = {
            "recommendation": getattr(governance_profile, "recommendation", None),
            "confidence_score": getattr(governance_profile, "confidence_score", None),
        }
        self.save()
        return item

    def active(self):
        return self._versions.get(self._active_version) if self._active_version else None

    def get(self, version: str):
        return self._versions.get(version)

    def list_versions(self):
        return list(self._versions.values())

    def save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"active_version": self._active_version, "versions": self._versions}, indent=2, default=str), encoding="utf-8")

    def load(self):
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self._active_version = payload.get("active_version")
        self._versions = dict(payload.get("versions", {}))
        return self
