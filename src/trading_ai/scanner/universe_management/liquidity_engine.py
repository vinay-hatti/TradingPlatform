from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .liquidity_policy import LiquidityGovernancePolicy
from .liquidity_profile import LiquidityEvaluation, LiquidityMetrics


class LiquidityGovernanceEngine:
    def __init__(self, policy: LiquidityGovernancePolicy | None = None) -> None:
        self.policy = policy or LiquidityGovernancePolicy()
        self.policy.validate()

    @staticmethod
    def _security_value(security: dict[str, Any], key: str, default=None):
        value = security.get(key, default)
        return value.strip() if isinstance(value, str) else value

    def evaluate(self, security: dict[str, Any], metrics: LiquidityMetrics | None, *, now: datetime | None = None) -> LiquidityEvaluation:
        now = now or datetime.now(timezone.utc)
        symbol = str(security.get("symbol", "")).upper()
        reasons: list[str] = []
        warnings: list[str] = []
        exchange = str(self._security_value(security, "exchange", "")).upper()
        asset_type = str(self._security_value(security, "asset_type", "EQUITY")).upper()
        options_eligible = str(self._security_value(security, "options_eligible", "false")).lower() in {"1", "true", "yes", "y"}
        if exchange and exchange not in self.policy.allowed_exchanges:
            reasons.append("EXCHANGE_NOT_ALLOWED")
        if asset_type == "ETF" and not self.policy.allow_etfs:
            reasons.append("ETF_NOT_ALLOWED")
        if self.policy.require_options_eligible and not options_eligible:
            reasons.append("OPTIONS_NOT_ELIGIBLE")
        if metrics is None:
            reasons.append("MISSING_METRICS")
            status = "REVIEW" if self.policy.missing_metric_action == "REVIEW" else "REJECTED"
            return LiquidityEvaluation(symbol, status, False, 0.0, tuple(reasons), tuple(warnings), None, security)
        age_hours = max(0.0, (now - metrics.as_of).total_seconds() / 3600)
        if age_hours > self.policy.maximum_market_data_age_hours:
            reasons.append("STALE_MARKET_DATA")
        if self.policy.reject_halted and metrics.halted:
            reasons.append("TRADING_HALTED")
        checks = (
            (metrics.price is not None and metrics.price < self.policy.minimum_price, "PRICE_BELOW_MINIMUM"),
            (metrics.price is not None and metrics.price > self.policy.maximum_price, "PRICE_ABOVE_MAXIMUM"),
            (metrics.average_daily_volume is not None and metrics.average_daily_volume < self.policy.minimum_average_daily_volume, "AVERAGE_VOLUME_BELOW_MINIMUM"),
            (metrics.average_daily_dollar_volume is not None and metrics.average_daily_dollar_volume < self.policy.minimum_average_daily_dollar_volume, "DOLLAR_VOLUME_BELOW_MINIMUM"),
            (metrics.bid_ask_spread_pct is not None and metrics.bid_ask_spread_pct > self.policy.maximum_bid_ask_spread_pct, "SPREAD_ABOVE_MAXIMUM"),
            (metrics.market_cap is not None and metrics.market_cap < self.policy.minimum_market_cap, "MARKET_CAP_BELOW_MINIMUM"),
            (metrics.option_volume is not None and metrics.option_volume < self.policy.minimum_option_volume, "OPTION_VOLUME_BELOW_MINIMUM"),
            (metrics.option_open_interest is not None and metrics.option_open_interest < self.policy.minimum_option_open_interest, "OPTION_OPEN_INTEREST_BELOW_MINIMUM"),
        )
        reasons.extend(reason for failed, reason in checks if failed)
        required = {
            "price": metrics.price,
            "average_daily_volume": metrics.average_daily_volume,
            "average_daily_dollar_volume": metrics.average_daily_dollar_volume,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            reasons.append("MISSING_METRICS")
            warnings.append("Missing required metrics: " + ", ".join(missing))
        optional_missing = [
            name for name, value in {
                "bid_ask_spread_pct": metrics.bid_ask_spread_pct,
                "market_cap": metrics.market_cap,
            }.items() if value is None
        ]
        if optional_missing:
            warnings.append("Missing optional metrics: " + ", ".join(optional_missing))
        reasons = sorted(set(reasons), key=lambda item: self.policy.rejection_reason_order.index(item) if item in self.policy.rejection_reason_order else 999)
        eligible = not reasons
        volume_ratio = min(1.0, (metrics.average_daily_volume or 0) / max(1, self.policy.minimum_average_daily_volume * 5))
        dollar_ratio = min(1.0, (metrics.average_daily_dollar_volume or 0.0) / max(1.0, self.policy.minimum_average_daily_dollar_volume * 5))
        spread_score = max(0.0, 1.0 - (metrics.bid_ask_spread_pct or 1.0) / max(self.policy.maximum_bid_ask_spread_pct, 0.0001))
        market_cap_ratio = min(1.0, (metrics.market_cap or 0.0) / max(1.0, self.policy.minimum_market_cap * 10))
        score = round(100.0 * (0.30 * volume_ratio + 0.35 * dollar_ratio + 0.20 * spread_score + 0.15 * market_cap_ratio), 2)
        return LiquidityEvaluation(symbol, "ELIGIBLE" if eligible else "REJECTED", eligible, score, tuple(reasons), tuple(warnings), metrics, security)
