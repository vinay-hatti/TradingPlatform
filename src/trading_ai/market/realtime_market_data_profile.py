from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str: return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class MarketDataSourceProfile:
    provider: str
    feed: str | None = None
    venue: str | None = None
    connection_id: str | None = None
    sequence_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RawQuoteEvent:
    symbol: str
    bid_price: Any
    ask_price: Any
    bid_size: Any = None
    ask_size: Any = None
    exchange_timestamp: Any = None
    provider_timestamp: Any = None
    received_timestamp: Any = None
    asset_class: str = "EQUITY"
    exchange: str | None = None
    bid_exchange: str | None = None
    ask_exchange: str | None = None
    conditions: tuple[str, ...] = ()
    source: MarketDataSourceProfile | dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RawTradeEvent:
    symbol: str
    price: Any
    size: Any = None
    exchange_timestamp: Any = None
    provider_timestamp: Any = None
    received_timestamp: Any = None
    asset_class: str = "EQUITY"
    exchange: str | None = None
    conditions: tuple[str, ...] = ()
    source: MarketDataSourceProfile | dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class NormalizedQuote:
    symbol: str; asset_class: str; bid_price: float; ask_price: float
    bid_size: float; ask_size: float; midpoint: float; spread: float; spread_pct: float
    exchange_timestamp: str; provider_timestamp: str | None; received_timestamp: str
    event_age_seconds: float; bid_exchange: str | None = None; ask_exchange: str | None = None
    conditions: tuple[str, ...] = (); source: MarketDataSourceProfile | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class NormalizedTrade:
    symbol: str; asset_class: str; price: float; size: float; notional: float
    exchange_timestamp: str; provider_timestamp: str | None; received_timestamp: str
    event_age_seconds: float; exchange: str | None = None; conditions: tuple[str, ...] = ()
    source: MarketDataSourceProfile | None = None; metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class MarketDataQualityCheck:
    name: str; category: str; passed: bool; required: bool; score: float
    severity: str; message: str; metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class MarketDataQualityProfile:
    event_type: str; symbol: str; valid: bool; allowed: bool; score: float
    grade: str; severity: str; recommendation: str; event_age_seconds: float | None = None
    stale: bool = False; out_of_order: bool = False; future_timestamp: bool = False
    checks: tuple[MarketDataQualityCheck, ...] = (); warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = (); metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

@dataclass(frozen=True)
class QuoteNormalizationResult:
    valid: bool; allowed: bool; quote: NormalizedQuote | None; quality: MarketDataQualityProfile
    warnings: tuple[str, ...] = (); rejection_reasons: tuple[str, ...] = ()
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class TradeNormalizationResult:
    valid: bool; allowed: bool; trade: NormalizedTrade | None; quality: MarketDataQualityProfile
    warnings: tuple[str, ...] = (); rejection_reasons: tuple[str, ...] = ()
    def to_dict(self): return asdict(self)
