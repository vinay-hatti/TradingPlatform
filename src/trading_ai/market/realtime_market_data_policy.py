from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RealTimeMarketDataPolicy:
    allowed_asset_classes: tuple[str, ...] = ("EQUITY", "OPTION", "ETF", "INDEX")
    maximum_quote_age_seconds: float = 5.0
    maximum_trade_age_seconds: float = 10.0
    maximum_future_skew_seconds: float = 2.0
    maximum_out_of_order_seconds: float = 1.0
    maximum_spread_pct: float = 0.25
    warning_spread_pct: float = 0.10
    minimum_bid_price: float = 0.0
    minimum_ask_price: float = 0.0
    minimum_trade_price: float = 0.0
    minimum_quote_size: float = 0.0
    minimum_trade_size: float = 0.0
    reject_crossed_quotes: bool = True
    reject_locked_quotes: bool = False
    reject_stale_quotes: bool = True
    reject_stale_trades: bool = False
    reject_future_timestamps: bool = True
    reject_out_of_order_events: bool = True
    require_provider_timestamp: bool = False
    require_positive_prices: bool = True
    require_symbol: bool = True
    fail_closed: bool = True
    minimum_quality_score: float = 80.0

    def validate(self) -> None:
        numeric_nonnegative = (
            self.maximum_quote_age_seconds, self.maximum_trade_age_seconds,
            self.maximum_future_skew_seconds, self.maximum_out_of_order_seconds,
            self.maximum_spread_pct, self.warning_spread_pct,
        )
        if any(v < 0 for v in numeric_nonnegative):
            raise ValueError("market-data thresholds cannot be negative")
        if self.warning_spread_pct > self.maximum_spread_pct:
            raise ValueError("warning_spread_pct cannot exceed maximum_spread_pct")
        if not 0 <= self.minimum_quality_score <= 100:
            raise ValueError("minimum_quality_score must be between 0 and 100")
