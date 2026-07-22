from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScannerFilter:
    min_institutional_score: float | None = None
    max_institutional_score: float | None = None
    min_probability_of_profit: float | None = None
    max_probability_of_profit: float | None = None
    min_liquidity_score: float | None = None
    min_open_interest: int | None = None
    min_volume: int | None = None
    max_spread_pct: float | None = None
    sectors: tuple[str, ...] = field(default_factory=tuple)
    directions: tuple[str, ...] = field(default_factory=tuple)
    strategy_types: tuple[str, ...] = field(default_factory=tuple)
    symbols: tuple[str, ...] = field(default_factory=tuple)
    exclude_symbols: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "sectors",
            "directions",
            "strategy_types",
            "symbols",
            "exclude_symbols",
        ):
            payload[key] = list(payload[key])
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScannerFilter":
        normalized = dict(payload)
        for key in (
            "sectors",
            "directions",
            "strategy_types",
            "symbols",
            "exclude_symbols",
        ):
            value = normalized.get(key)
            if value is None:
                normalized[key] = ()
            elif isinstance(value, str):
                normalized[key] = tuple(
                    part.strip() for part in value.split(",") if part.strip()
                )
            else:
                normalized[key] = tuple(str(item) for item in value)
        return cls(**normalized)


@dataclass(frozen=True)
class SavedScannerView:
    name: str
    filters: ScannerFilter
    sort_field: str = "institutional_score"
    sort_direction: str = "DESC"
    top_n: int = 50
    page_size: int = 25
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "filters": self.filters.to_dict(),
            "sort_field": self.sort_field,
            "sort_direction": self.sort_direction,
            "top_n": self.top_n,
            "page_size": self.page_size,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SavedScannerView":
        return cls(
            name=str(payload["name"]),
            description=str(payload.get("description", "")),
            filters=ScannerFilter.from_dict(payload.get("filters", {})),
            sort_field=str(payload.get("sort_field", "institutional_score")),
            sort_direction=str(payload.get("sort_direction", "DESC")).upper(),
            top_n=int(payload.get("top_n", 50)),
            page_size=int(payload.get("page_size", 25)),
        )
