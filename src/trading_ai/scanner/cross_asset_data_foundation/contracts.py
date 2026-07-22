from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any

class AssetClass(str, Enum):
    EQUITY_INDEX = "EQUITY_INDEX"
    VOLATILITY = "VOLATILITY"
    TREASURY = "TREASURY"
    CREDIT = "CREDIT"
    COMMODITY = "COMMODITY"
    CURRENCY = "CURRENCY"
    SECTOR = "SECTOR"

class CrossAssetGovernanceStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    EXCLUDED = "EXCLUDED"

@dataclass(frozen=True)
class CrossAssetUniverseMember:
    symbol: str
    asset_class: AssetClass
    group: str
    benchmark_symbol: str | None = None
    enabled: bool = True

@dataclass(frozen=True)
class CrossAssetFeatureProfile:
    symbol: str
    asset_class: AssetClass
    group: str
    benchmark_symbol: str | None
    as_of_date: date
    observation_count: int
    latest_close: float | None
    latest_volume: float | None
    return_1d: float | None
    return_5d: float | None
    return_21d: float | None
    realized_volatility_21d: float | None
    atr_14: float | None
    atr_pct_14: float | None
    ema_20: float | None
    ema_50: float | None
    trend_direction: str
    trend_strength: float | None
    volatility_regime: str
    benchmark_return_21d: float | None
    relative_strength_21d: float | None
    volume_ratio_20d: float | None
    liquidity_regime: str
    governance_status: CrossAssetGovernanceStatus
    governance_reasons: tuple[str, ...]
    feature_version: str = "m35.phase5.step1.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class CrossAssetRunProfile:
    as_of_date: date
    generated_at: datetime
    source_table: str
    output_path: str
    universe_size: int
    symbols_read: int
    symbols_generated: int
    ready_count: int
    review_count: int
    excluded_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
