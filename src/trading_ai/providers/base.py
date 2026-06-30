from abc import ABC, abstractmethod
import pandas as pd


class MarketDataProvider(ABC):

    @abstractmethod
    def get_history(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        pass

    @abstractmethod
    def get_option_chain(self, symbol: str, expiration: str):
        pass

    @abstractmethod
    def get_quote(self, symbol: str):
        pass
