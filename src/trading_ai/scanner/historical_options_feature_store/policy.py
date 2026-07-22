from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HistoricalOptionFeaturePolicy:
    allowed_readiness_statuses: tuple[str, ...] = ("READY",)
    minimum_days_to_expiration: int = 1
    maximum_days_to_expiration: int = 365
    minimum_open_interest: int = 1
    minimum_volume: int = 0
    require_implied_volatility: bool = True
    require_delta: bool = True
    review_missing_optional_greeks: bool = True

    def normalized_allowed_statuses(self) -> set[str]:
        return {
            str(value).strip().upper()
            for value in self.allowed_readiness_statuses
            if str(value).strip()
        }
