from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class OptionContractInspection:
    symbol: str
    expiry: str
    strike: float
    option_type: str
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    spread_pct: float | None = None
    mid_price: float | None = None
    liquidity_status: str = "UNKNOWN"
    warnings: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class OptionChainInspectionProfile:
    symbol: str
    quote_date: str | None
    underlying_price: float | None
    total_contracts: int
    filtered_contracts: int
    expiries: tuple[str, ...]
    calls: tuple[OptionContractInspection, ...]
    puts: tuple[OptionContractInspection, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    rejection_counts: dict[str, int] = field(default_factory=dict)
    field_coverage: dict[str, int] = field(default_factory=dict)
    observed_ranges: dict[str, dict[str, float | int | None]] = field(
        default_factory=dict
    )
    quote_policy: str = "STRICT"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quote_date": self.quote_date,
            "underlying_price": self.underlying_price,
            "total_contracts": self.total_contracts,
            "filtered_contracts": self.filtered_contracts,
            "expiries": list(self.expiries),
            "calls": [item.to_dict() for item in self.calls],
            "puts": [item.to_dict() for item in self.puts],
            "warnings": list(self.warnings),
            "rejection_counts": dict(self.rejection_counts),
            "field_coverage": dict(self.field_coverage),
            "observed_ranges": dict(self.observed_ranges),
            "quote_policy": self.quote_policy,
        }
