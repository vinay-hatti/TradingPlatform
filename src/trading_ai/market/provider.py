from abc import ABC, abstractmethod
import pandas as pd


class MarketDataProvider(ABC):

    @abstractmethod
    def history(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        pass

    @abstractmethod
    def quote(self, symbol: str) -> dict:
        pass
