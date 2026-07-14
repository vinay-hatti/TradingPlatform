from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


class WalkForwardParameterRegistry:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._versions: dict[str, dict[str, Any]] = {}
        self._active_version: str | None = None
        if self.path and self.path.exists():
            self.load()

    def register(self, version: str, parameters: dict[str, Any], profile: Any = None, activate: bool = False, metadata: dict[str, Any] | None = None):
        if not version:
            raise ValueError("version is required")
        self._versions[version] = {
            "version": version,
            "parameters": dict(parameters or {}),
            "profile": self._serialize(profile),
            "metadata": dict(metadata or {}),
        }
        if activate or self._active_version is None:
            self._active_version = version
        self.save()
        return self._versions[version]

    def activate(self, version: str):
        if version not in self._versions:
            raise KeyError(version)
        self._active_version = version
        self.save()
        return self._versions[version]

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

    @staticmethod
    def _serialize(value):
        if value is None:
            return None
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return {str(k): WalkForwardParameterRegistry._serialize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [WalkForwardParameterRegistry._serialize(v) for v in value]
        return value
