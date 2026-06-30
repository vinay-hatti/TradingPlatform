from dataclasses import dataclass


@dataclass
class BacktestConfig:
    symbols: list[str]
    start: str
    end: str

    initial_capital: float = 100000.0
    risk_per_trade_pct: float = 0.01
    max_contracts: int = 5

    stop_loss_pct: float = -0.08
    take_profit_pct: float = 0.15
    max_holding_bars: int = 10
    min_call_score: float = 60.0
    min_put_score: float = 60.0
    min_option_price: float = 0.50
    min_abs_delta: float = 0.30
    max_abs_delta: float = 0.70
    allowed_regimes: list[str] | None = None
    allowed_strategies: list[str] | None = None
