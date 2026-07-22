from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniversePolicy:
    minimum_symbol_count: int = 6000
    allowed_asset_types: tuple[str, ...] = ("EQUITY", "ETF")
    allowed_exchanges: tuple[str, ...] = (
        "NASDAQ",
        "NYSE",
        "NYSE_AMERICAN",
        "NYSE_ARCA",
        "CBOE",
    )
    require_active: bool = True
    require_tradable: bool = True
    reject_duplicate_symbols: bool = True
    reject_blank_symbols: bool = True

    def validate(self) -> None:
        if self.minimum_symbol_count <= 0:
            raise ValueError("minimum_symbol_count must be greater than zero.")
        if not self.allowed_asset_types:
            raise ValueError("allowed_asset_types cannot be empty.")
        if not self.allowed_exchanges:
            raise ValueError("allowed_exchanges cannot be empty.")
