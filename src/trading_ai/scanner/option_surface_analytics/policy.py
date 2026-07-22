from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptionSurfaceAnalyticsPolicy:
    allowed_feature_statuses: tuple[str, ...] = ("READY",)

    minimum_contracts_per_expiration: int = 10
    minimum_strikes_per_expiration: int = 5
    minimum_open_interest_per_expiration: int = 100
    minimum_expirations_per_symbol: int = 1

    near_money_absolute_delta_minimum: float = 0.40
    near_money_absolute_delta_maximum: float = 0.60

    downside_put_absolute_delta_minimum: float = 0.15
    downside_put_absolute_delta_maximum: float = 0.35

    upside_call_absolute_delta_minimum: float = 0.15
    upside_call_absolute_delta_maximum: float = 0.35

    concentration_top_n: int = 5
    maximum_ready_open_interest_concentration: float = 0.80
    maximum_review_open_interest_concentration: float = 0.95

    minimum_atm_term_points_for_ready: int = 2

    def normalized_allowed_statuses(self) -> set[str]:
        return {
            str(value).strip().upper()
            for value in self.allowed_feature_statuses
            if str(value).strip()
        }
