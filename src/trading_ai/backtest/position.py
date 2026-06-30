from dataclasses import dataclass
from typing import Optional


@dataclass
class Position:
    symbol: str
    signal: str
    strategy: str

    entry_index: int

    stock_entry_price: float
    option_entry_price: float

    strike: float
    expiry: str
    delta: float

    size: float
    score: float
    regime: str = ""

    exit_index: Optional[int] = None

    stock_exit_price: Optional[float] = None
    option_exit_price: Optional[float] = None

    exit_reason: str = ""

    pnl: float = 0.0
    closed: bool = False

    def mark_pnl(self, option_price: float) -> float:

        self.option_exit_price = option_price

        self.pnl = (
            option_price - self.option_entry_price
        ) * self.size * 100

        return self.pnl

    def close(
        self,
        index: int,
        stock_price: float,
        option_price: float,
        reason: str,
    ):
        self.exit_index = index
        self.stock_exit_price = stock_price
        self.option_exit_price = option_price
        self.exit_reason = reason
        self.closed = True
        self.mark_pnl(option_price)
