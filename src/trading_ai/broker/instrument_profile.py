from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass(frozen=True)
class EquityInstrumentProfile:
    symbol: str
    broker_symbol: str
    exchange: str | None = None
    currency: str = "USD"
    asset_class: str = "EQUITY"
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class OptionInstrumentProfile:
    underlying_symbol: str
    broker_underlying_symbol: str
    expiration: str
    strike: float
    option_type: str
    multiplier: int = 100
    occ_symbol: str | None = None
    broker_symbol: str | None = None
    exchange: str | None = None
    currency: str = "USD"
    asset_class: str = "OPTION"
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class InstrumentMappingProfile:
    valid: bool
    allowed: bool
    asset_class: str
    canonical_symbol: str
    broker_symbol: str | None
    equity: EquityInstrumentProfile | None = None
    option: OptionInstrumentProfile | None = None
    score: float = 0.0
    grade: str = "F"
    severity: str = "CRITICAL"
    recommendation: str = "REJECT"
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
