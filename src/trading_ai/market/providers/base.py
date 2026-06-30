from abc import ABC, abstractmethod
from typing import List
import pandas as pd

from trading_ai.domain.market import MarketBar


class MarketDataProvider(ABC):

    @abstractmethod
    def fetch_history(self, symbol: str, start: str, end: str) -> List[MarketBar]:
        pass

    def to_dataframe(self, bars: List[MarketBar]) -> pd.DataFrame:

        return pd.DataFrame([bar.__dict__ for bar in bars])
