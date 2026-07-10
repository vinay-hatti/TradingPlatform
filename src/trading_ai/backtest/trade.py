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

    entry_delta: float = 0.0
    entry_gamma: float = 0.0
    entry_theta: float = 0.0
    entry_vega: float = 0.0
    entry_rho: float = 0.0
    entry_iv: float = 0.0
    entry_dte: int = 0
    entry_volatility: float = 0.0

    # Reporting / diagnostics metadata
    market_regime: str = "UNKNOWN"
    regime: str = "UNKNOWN"

    pricing_source: str = ""
    entry_pricing_source: str = ""
    exit_pricing_source: str = "black_scholes_mark_to_model"
    option_symbol: str = ""
    option_volume: int = 0
    option_open_interest: int = 0
    option_spread_pct: float = 0.0

    position_size: float = 0.0
    initial_risk: float = 0.0
    r_multiple: float = 0.0
    model_exit_price: float = 0.0
