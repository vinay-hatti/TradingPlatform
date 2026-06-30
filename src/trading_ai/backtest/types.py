from dataclasses import dataclass
from datetime import datetime


@dataclass
class Fill:
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: datetime


@dataclass
class TradeResult:
    symbol: str
    entry_price: float
    exit_price: float
    pnl: float
    return_pct: float
    days_held: int
    strategy: str
