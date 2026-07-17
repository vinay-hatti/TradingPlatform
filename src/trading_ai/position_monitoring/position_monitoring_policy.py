from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionMonitoringPolicy:
    """Govern real-time position snapshots and intraday risk state."""

    maximum_quote_age_seconds: int = 30
    maximum_snapshot_age_seconds: int = 60
    require_positive_mark_price: bool = True
    reject_missing_quotes: bool = True
    reject_stale_quotes: bool = True
    reject_duplicate_position_ids: bool = True
    require_account_consistency: bool = True
    require_non_negative_starting_equity: bool = True
    calculate_gross_and_net_exposure: bool = True
    calculate_intraday_drawdown: bool = True
    persist_snapshots: bool = True
    maximum_positions_per_snapshot: int = 1000
    minimum_snapshot_score: float = 85.0
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_quote_age_seconds <= 0:
            raise ValueError("maximum_quote_age_seconds must be positive")
        if self.maximum_snapshot_age_seconds <= 0:
            raise ValueError("maximum_snapshot_age_seconds must be positive")
        if self.maximum_positions_per_snapshot <= 0:
            raise ValueError("maximum_positions_per_snapshot must be positive")
        if not 0 <= self.minimum_snapshot_score <= 100:
            raise ValueError("minimum_snapshot_score must be between 0 and 100")
