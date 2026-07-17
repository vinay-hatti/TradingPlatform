from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperExecutionPolicy:
    """Govern deterministic paper-broker execution and fill simulation."""

    allowed_order_types: tuple[str, ...] = ("MARKET", "LIMIT", "STOP", "STOP_LIMIT")
    allowed_time_in_force: tuple[str, ...] = ("DAY", "GTC", "IOC", "FOK")
    default_latency_ms: int = 100
    minimum_latency_ms: int = 0
    maximum_latency_ms: int = 10000
    default_slippage_bps: float = 2.0
    maximum_slippage_bps: float = 100.0
    option_contract_commission: float = 0.65
    equity_per_share_commission: float = 0.0
    minimum_commission_per_order: float = 0.0
    maximum_fill_fraction_per_attempt: float = 1.0
    allow_partial_fills: bool = True
    require_marketable_limit: bool = True
    reject_stale_quotes: bool = True
    maximum_quote_age_seconds: int = 30
    reject_duplicate_execution_key: bool = True
    persist_execution_records: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if self.default_latency_ms < self.minimum_latency_ms:
            raise ValueError("default_latency_ms cannot be below minimum")
        if self.default_latency_ms > self.maximum_latency_ms:
            raise ValueError("default_latency_ms cannot exceed maximum")
        if not 0 <= self.default_slippage_bps <= self.maximum_slippage_bps:
            raise ValueError("default_slippage_bps is outside allowed range")
        if self.option_contract_commission < 0:
            raise ValueError("option_contract_commission cannot be negative")
        if self.equity_per_share_commission < 0:
            raise ValueError("equity_per_share_commission cannot be negative")
        if self.minimum_commission_per_order < 0:
            raise ValueError("minimum_commission_per_order cannot be negative")
        if not 0 < self.maximum_fill_fraction_per_attempt <= 1:
            raise ValueError(
                "maximum_fill_fraction_per_attempt must be in (0, 1]"
            )
        if self.maximum_quote_age_seconds <= 0:
            raise ValueError("maximum_quote_age_seconds must be positive")
