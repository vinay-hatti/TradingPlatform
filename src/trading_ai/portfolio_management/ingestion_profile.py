from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .profile import utc_now_iso


@dataclass(frozen=True)
class PortfolioIntakeRecord:
    intake_id: str
    portfolio_id: str
    symbol: str
    direction: str
    strategy_id: str
    strategy_type: str
    decision: str
    intake_status: str
    paper_trade_ready: bool
    execution_status: str
    estimated_entry_price: float | None
    maximum_loss: float | None
    maximum_profit: float | None
    reward_risk_ratio: float | None
    institutional_score: float | None
    source_artifact: str
    source_fingerprint: str
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class PortfolioIntakeSnapshot:
    portfolio_id: str
    records: tuple[PortfolioIntakeRecord, ...]
    generated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "record_count": len(self.records),
            "records": [record.to_dict() for record in self.records],
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class PortfolioIngestionResult:
    source_type: str
    source_artifact: str
    status: str
    symbol: str = ""
    strategy_id: str = ""
    intake_id: str = ""
    position_id: str = ""
    imported: bool = False
    duplicate: bool = False
    marked: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload
