from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LiquidityGovernancePolicy:
    minimum_price: float = 5.0
    maximum_price: float = 5000.0
    minimum_average_daily_volume: int = 200_000
    minimum_average_daily_dollar_volume: float = 10_000_000.0
    maximum_bid_ask_spread_pct: float = 0.05
    minimum_market_cap: float = 300_000_000.0
    minimum_option_volume: int = 0
    minimum_option_open_interest: int = 0
    require_options_eligible: bool = False
    allow_etfs: bool = True
    allowed_exchanges: tuple[str, ...] = (
        "NASDAQ", "NYSE", "NYSE_AMERICAN", "NYSE_ARCA", "CBOE", "IEX"
    )
    reject_halted: bool = True
    maximum_market_data_age_hours: int = 48
    missing_metric_action: str = "REJECT"
    rejection_reason_order: tuple[str, ...] = field(default=(
        "MISSING_METRICS", "STALE_MARKET_DATA", "TRADING_HALTED", "EXCHANGE_NOT_ALLOWED",
        "ETF_NOT_ALLOWED", "OPTIONS_NOT_ELIGIBLE", "PRICE_BELOW_MINIMUM", "PRICE_ABOVE_MAXIMUM",
        "AVERAGE_VOLUME_BELOW_MINIMUM", "DOLLAR_VOLUME_BELOW_MINIMUM", "SPREAD_ABOVE_MAXIMUM",
        "MARKET_CAP_BELOW_MINIMUM", "OPTION_VOLUME_BELOW_MINIMUM", "OPTION_OPEN_INTEREST_BELOW_MINIMUM",
    ))

    def validate(self) -> None:
        if self.minimum_price < 0 or self.maximum_price <= self.minimum_price:
            raise ValueError("price thresholds are invalid")
        if self.minimum_average_daily_volume < 0 or self.minimum_average_daily_dollar_volume < 0:
            raise ValueError("volume thresholds cannot be negative")
        if not 0 <= self.maximum_bid_ask_spread_pct <= 1:
            raise ValueError("maximum_bid_ask_spread_pct must be between zero and one")
        if self.maximum_market_data_age_hours <= 0:
            raise ValueError("maximum_market_data_age_hours must be greater than zero")
        if self.missing_metric_action not in {"REJECT", "REVIEW"}:
            raise ValueError("missing_metric_action must be REJECT or REVIEW")
