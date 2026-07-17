from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .production_runtime_profile import ProductionConfigurationProfile


class ProductionConfigurationLoader:
    """Load root-level config JSON with environment overlay and env overrides."""

    ENV_PREFIX = "TRADING_AI__"

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()

    @staticmethod
    def _merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
        result = deepcopy(base)
        for key, value in override.items():
            if isinstance(value, Mapping) and isinstance(result.get(key), dict):
                result[key] = ProductionConfigurationLoader._merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    @staticmethod
    def _coerce(value: str) -> Any:
        lowered = value.strip().lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        if lowered in {"none", "null"}:
            return None
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            return value

    @classmethod
    def _apply_env_overrides(cls, config: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(config)
        for name, raw in os.environ.items():
            if not name.startswith(cls.ENV_PREFIX):
                continue
            parts = [p.lower() for p in name[len(cls.ENV_PREFIX):].split("__") if p]
            if not parts:
                continue
            cursor = result
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = cls._coerce(raw)
        return result

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Configuration file must contain an object: {path}")
        return payload

    def load(
        self,
        environment: str | None = None,
        base_file: str = "config/runtime.json",
    ) -> ProductionConfigurationProfile:
        env = (
            environment
            or os.getenv("TRADING_AI_ENV")
            or os.getenv("APP_ENV")
            or "development"
        ).strip().lower()

        base_path = self.project_root / base_file
        env_path = self.project_root / "config" / f"runtime.{env}.json"
        merged = self._merge(self._read_json(base_path), self._read_json(env_path))
        merged = self._apply_env_overrides(merged)

        paths = merged.get("paths", {})
        providers = merged.get("providers", {})
        trading = merged.get("trading", {})

        return ProductionConfigurationProfile(
            environment=env,
            debug=bool(merged.get("debug", False)),
            live_trading_enabled=bool(trading.get("live_enabled", False)),
            paper_trading_enabled=bool(trading.get("paper_enabled", env != "production")),
            kill_switch_enabled=bool(trading.get("kill_switch_enabled", True)),
            database_url=merged.get("database_url"),
            broker_provider=providers.get("broker"),
            market_data_provider=providers.get("market_data"),
            data_directory=str(paths.get("data", "data")),
            reports_directory=str(paths.get("reports", "reports")),
            logs_directory=str(paths.get("logs", "logs")),
            audit_directory=str(paths.get("audit", "logs/audit")),
            required_secrets=tuple(merged.get("required_secrets", ())),
            feature_flags=dict(merged.get("feature_flags", {})),
            source_files=tuple(
                str(p.relative_to(self.project_root))
                for p in (base_path, env_path)
                if p.exists()
            ),
            metadata={"project_root": str(self.project_root)},
        )
