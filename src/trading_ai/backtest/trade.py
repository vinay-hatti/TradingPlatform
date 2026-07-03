from dataclasses import dataclass
from datetime import date


@dataclass
class BacktestTrade:
    symbol: str

    entry_date: date
    exit_date: date

    strategy: str
    signal: str

    strike: float
    expiry: str

    entry_price: float
    exit_price: float

    contracts: int

    pnl: float
    pnl_pct: float

    max_profit: float
    max_drawdown: float

    days_held: int

    exit_reason: str

    rank_score: float
    option_score: float
    pop: float
    liquidity: float
    atm_score: float

    gross_pnl: float = 0.0
    fees: float = 0.0
    net_pnl: float = 0.0
