from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketBar:
    symbol: str
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
