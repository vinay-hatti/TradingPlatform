from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_ai.strategy_engine.execution_route_registry_profile import (
    ExecutionRoutePromotionProfile,
    ExecutionRouteRegistryProfile,
    ExecutionRouteVersionProfile,
)
from trading_ai.strategy_engine.execution_route_registry_serialization import execution_route_registry_to_dict


class ExecutionRouteRegistry:
    """Persistent, auditable registry for execution route versions."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._versions: dict[str, dict[str, Any]] = {}
        self._active_version: str | None = None
        self._champion_version: str | None = None
        self._audit_log: list[dict[str, Any]] = []
        if self.path and self.path.exists():
            self.load()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _value(item: Any, name: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(name, default)
        return getattr(item, name, default)

    def register(self, version: str, route: Any, *, activate: bool = False, champion: bool = False, challenger: bool = False, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        version = str(version or "").strip()
        if not version:
            raise ValueError("version is required")
        if version in self._versions:
            raise ValueError(f"Route version already exists: {version}")
        now = self._now()
        record = {
            "version": version,
            "route_type": str(self._value(route, "route_type", "VENUE")).upper(),
            "route_name": str(self._value(route, "route_name", "UNKNOWN")),
            "status": "REGISTERED",
            "observation_count": int(self._value(route, "observation_count", 0) or 0),
            "route_score": float(self._value(route, "route_score", 0.0) or 0.0),
            "confidence_score": float(self._value(route, "confidence_score", 0.0) or 0.0),
            "average_shortfall_bps": float(self._value(route, "average_shortfall_bps", 0.0) or 0.0),
            "average_fill_ratio": float(self._value(route, "average_fill_ratio", 0.0) or 0.0),
            "average_latency_seconds": float(self._value(route, "average_latency_seconds", 0.0) or 0.0),
            "average_spread_bps": float(self._value(route, "average_spread_bps", 0.0) or 0.0),
            "governance_score": float(self._value(route, "governance_score", 0.0) or 0.0),
            "governance_grade": str(self._value(route, "governance_grade", "N/A")),
            "governance_severity": str(self._value(route, "governance_severity", "UNKNOWN")),
            "governance_allowed": bool(self._value(route, "governance_allowed", True)),
            "active": False, "champion": False, "challenger": bool(challenger),
            "valid": True, "created_at": now, "activated_at": "", "retired_at": "",
            "warnings": list(self._value(route, "warnings", ()) or ()),
            "rejection_reasons": list(self._value(route, "rejection_reasons", ()) or ()),
            "metadata": dict(metadata or self._value(route, "metadata", {}) or {}),
        }
        self._versions[version] = record
        self._audit("REGISTER", version, {"route_name": record["route_name"]})
        if activate or champion or self._active_version is None:
            self.activate(version, champion=champion or self._champion_version is None)
        self.save()
        return dict(self._versions[version])

    def activate(self, version: str, *, champion: bool = False) -> dict[str, Any]:
        if version not in self._versions:
            raise KeyError(f"Unknown route version: {version}")
        for record in self._versions.values():
            record["active"] = False
        record = self._versions[version]
        record["active"] = True
        record["status"] = "ACTIVE"
        record["activated_at"] = self._now()
        self._active_version = version
        if champion:
            self.set_champion(version)
        self._audit("ACTIVATE", version, {"champion": champion})
        self.save()
        return dict(record)

    def set_champion(self, version: str) -> dict[str, Any]:
        if version not in self._versions:
            raise KeyError(f"Unknown route version: {version}")
        for record in self._versions.values():
            record["champion"] = False
        record = self._versions[version]
        record["champion"] = True
        record["challenger"] = False
        record["status"] = "CHAMPION"
        self._champion_version = version
        self._audit("SET_CHAMPION", version, {})
        self.save()
        return dict(record)

    def mark_challenger(self, version: str) -> dict[str, Any]:
        if version not in self._versions:
            raise KeyError(f"Unknown route version: {version}")
        record = self._versions[version]
        record["challenger"] = True
        if not record["champion"]:
            record["status"] = "CHALLENGER"
        self._audit("MARK_CHALLENGER", version, {})
        self.save()
        return dict(record)

    def retire(self, version: str, reason: str = "") -> dict[str, Any]:
        if version not in self._versions:
            raise KeyError(f"Unknown route version: {version}")
        record = self._versions[version]
        record.update({"active": False, "champion": False, "challenger": False, "status": "RETIRED", "retired_at": self._now()})
        if self._active_version == version: self._active_version = None
        if self._champion_version == version: self._champion_version = None
        self._audit("RETIRE", version, {"reason": reason})
        self.save()
        return dict(record)

    def promote(self, promotion: ExecutionRoutePromotionProfile, *, actor: str = "SYSTEM") -> ExecutionRoutePromotionProfile:
        if not promotion.valid or not promotion.allowed:
            raise ValueError("Promotion profile is not approved")
        version = promotion.challenger_version
        if version not in self._versions:
            raise KeyError(f"Unknown challenger route version: {version}")
        old = self._champion_version
        if old and old in self._versions and old != version:
            self._versions[old]["champion"] = False
            self._versions[old]["active"] = False
            self._versions[old]["status"] = "SUPERSEDED"
        self.activate(version, champion=True)
        self._audit("PROMOTE", version, {"previous_champion": old, "actor": actor, "promotion_score": promotion.promotion_score})
        self.save()
        return replace(promotion, promoted=True, recommendation="PROMOTED")

    def active(self): return dict(self._versions[self._active_version]) if self._active_version in self._versions else None
    def champion(self): return dict(self._versions[self._champion_version]) if self._champion_version in self._versions else None
    def get(self, version: str): return dict(self._versions[version]) if version in self._versions else None
    def list_versions(self): return [dict(v) for v in self._versions.values()]
    def audit_log(self): return [dict(v) for v in self._audit_log]

    def profile(self) -> ExecutionRouteRegistryProfile:
        versions = tuple(ExecutionRouteVersionProfile(**{k: tuple(v) if k in {"warnings", "rejection_reasons"} else v for k, v in record.items() if k in ExecutionRouteVersionProfile.__dataclass_fields__}) for record in self._versions.values())
        return ExecutionRouteRegistryProfile(
            valid=bool(versions), route_count=len(versions), active_version=self._active_version or "UNAVAILABLE",
            champion_version=self._champion_version or "UNAVAILABLE",
            challenger_versions=tuple(v.version for v in versions if v.challenger),
            retired_versions=tuple(v.version for v in versions if v.status == "RETIRED"),
            versions=versions, audit_event_count=len(self._audit_log),
            warnings=() if versions else ("No execution routes are registered.",),
            metadata={"path": str(self.path) if self.path else None},
        )

    def save(self) -> None:
        if not self.path: return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload={"active_version": self._active_version, "champion_version": self._champion_version, "versions": self._versions, "audit_log": self._audit_log}
        self.path.write_text(json.dumps(execution_route_registry_to_dict(payload), indent=2, sort_keys=True), encoding="utf-8")

    def load(self):
        payload=json.loads(self.path.read_text(encoding="utf-8"))
        self._active_version=payload.get("active_version"); self._champion_version=payload.get("champion_version")
        self._versions=dict(payload.get("versions", {})); self._audit_log=list(payload.get("audit_log", []))
        return self

    def _audit(self, event: str, version: str, details: dict[str, Any]) -> None:
        self._audit_log.append({"timestamp": self._now(), "event": event, "version": version, "details": dict(details or {})})
