from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class RuntimeCheckProfile:
    name: str
    category: str
    passed: bool
    required: bool = True
    score: float = 100.0
    severity: str = "LOW"
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SecretResolutionProfile:
    name: str
    resolved: bool
    provider: str = "unavailable"
    required: bool = True
    redacted_value: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductionConfigurationProfile:
    environment: str
    debug: bool
    live_trading_enabled: bool
    paper_trading_enabled: bool
    kill_switch_enabled: bool
    database_url: str | None
    broker_provider: str | None
    market_data_provider: str | None
    data_directory: str
    reports_directory: str
    logs_directory: str
    audit_directory: str
    required_secrets: tuple[str, ...] = ()
    feature_flags: dict[str, bool] = field(default_factory=dict)
    source_files: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductionRuntimeProfile:
    valid: bool
    allowed: bool
    environment: str
    score: float
    grade: str
    severity: str
    recommendation: str
    checks: tuple[RuntimeCheckProfile, ...] = ()
    resolved_secrets: tuple[SecretResolutionProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    configuration: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
