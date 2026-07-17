from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class MarketDataReconciliationPolicy:
    maximum_price_difference_pct: float = 0.01
    warning_price_difference_pct: float = 0.005
    maximum_volume_difference_pct: float = 0.20
    warning_volume_difference_pct: float = 0.10
    maximum_timestamp_difference_seconds: float = 60.0
    minimum_reconciliation_score: float = 85.0
    require_live_value: bool = True
    require_historical_value: bool = True
    reject_symbol_mismatch: bool = True
    reject_timestamp_mismatch: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_price_difference_pct < 0:
            raise ValueError("maximum_price_difference_pct cannot be negative")
        if not 0 <= self.warning_price_difference_pct <= self.maximum_price_difference_pct:
            raise ValueError("invalid warning_price_difference_pct")
        if self.maximum_volume_difference_pct < 0:
            raise ValueError("maximum_volume_difference_pct cannot be negative")
        if not 0 <= self.warning_volume_difference_pct <= self.maximum_volume_difference_pct:
            raise ValueError("invalid warning_volume_difference_pct")
        if self.maximum_timestamp_difference_seconds < 0:
            raise ValueError("maximum_timestamp_difference_seconds cannot be negative")
        if not 0 <= self.minimum_reconciliation_score <= 100:
            raise ValueError("minimum_reconciliation_score must be between 0 and 100")
