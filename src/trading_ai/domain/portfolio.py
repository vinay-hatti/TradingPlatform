from dataclasses import dataclass
from typing import List
from trading_ai.domain.trading import TradeRecommendation


@dataclass
class Position:
    symbol: str
    quantity: int
    entry_price: float


@dataclass
class Portfolio:
    cash: float
    positions: List[Position]
    open_trades: List[TradeRecommendation]
