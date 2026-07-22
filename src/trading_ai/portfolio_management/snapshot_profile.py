from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .profile import utc_now_iso


@dataclass(frozen=True)
class ExposureBucket:
    key: str
    position_count: int
    capital_committed: float
    capital_pct: float
    unrealized_pnl: float
    realized_pnl: float
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioExposureView:
    portfolio_id: str
    generated_at: str
    net_liquidation_value: float
    cash_balance: float
    capital_committed: float
    capital_utilization_pct: float
    cash_pct: float
    open_position_count: int
    total_unrealized_pnl: float
    total_realized_pnl: float
    aggregate_delta: float
    aggregate_gamma: float
    aggregate_theta: float
    aggregate_vega: float
    aggregate_rho: float
    largest_symbol_pct: float
    largest_sector_pct: float
    by_symbol: tuple[ExposureBucket, ...] = field(default_factory=tuple)
    by_sector: tuple[ExposureBucket, ...] = field(default_factory=tuple)
    by_strategy: tuple[ExposureBucket, ...] = field(default_factory=tuple)
    by_direction: tuple[ExposureBucket, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "by_symbol": [item.to_dict() for item in self.by_symbol],
            "by_sector": [item.to_dict() for item in self.by_sector],
            "by_strategy": [item.to_dict() for item in self.by_strategy],
            "by_direction": [item.to_dict() for item in self.by_direction],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PortfolioAuditRecord:
    audit_id: str
    portfolio_id: str
    snapshot_id: str
    event_type: str
    occurred_at: str
    registry_fingerprint: str
    open_position_count: int
    closed_position_count: int
    cash_balance: float
    net_liquidation_value: float
    capital_committed: float
    realized_pnl: float
    unrealized_pnl: float
    source_registry: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioSnapshotArtifact:
    snapshot_id: str
    portfolio_id: str
    generated_at: str
    registry_fingerprint: str
    registry: dict[str, Any]
    exposure: PortfolioExposureView
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "portfolio_id": self.portfolio_id,
            "generated_at": self.generated_at,
            "registry_fingerprint": self.registry_fingerprint,
            "registry": self.registry,
            "exposure": self.exposure.to_dict(),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PortfolioAuditHistory:
    portfolio_id: str
    records: tuple[PortfolioAuditRecord, ...] = field(default_factory=tuple)
    generated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "record_count": len(self.records),
            "records": [item.to_dict() for item in self.records],
            "generated_at": self.generated_at,
        }
