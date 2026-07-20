from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class OptionLiquiditySnapshot:
    symbol: str
    quote_date: date
    option_volume: int
    open_interest: int
    median_spread_pct: float
    iv_rank: float
    iv_percentile: float
    contract_count: int
    liquid_contract_count: int
