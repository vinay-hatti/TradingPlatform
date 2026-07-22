from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketDataPopulationPolicy:
    lookback_days: int = 90
    minimum_bars: int = 20
    stale_after_days: int = 7
    minimum_coverage_pct: float = 70.0
    batch_size: int = 100
    max_retries: int = 3
    retry_backoff_seconds: float = 5.0
    request_pause_seconds: float = 1.0
    continue_on_error: bool = True
    minimum_fd_headroom: int = 64
    collect_resources_each_batch: bool = True

    def validate(self) -> None:
        if self.lookback_days < 1:
            raise ValueError("lookback_days must be positive")
        if self.minimum_bars < 1:
            raise ValueError("minimum_bars must be positive")
        if self.stale_after_days < 0:
            raise ValueError("stale_after_days cannot be negative")
        if not 0.0 <= self.minimum_coverage_pct <= 100.0:
            raise ValueError("minimum_coverage_pct must be between 0 and 100")
        if self.batch_size < 1:
            raise ValueError("batch_size must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if self.retry_backoff_seconds < 0 or self.request_pause_seconds < 0:
            raise ValueError("timing values cannot be negative")
        if self.minimum_fd_headroom < 1:
            raise ValueError("minimum_fd_headroom must be positive")
