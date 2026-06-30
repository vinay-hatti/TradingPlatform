from dataclasses import dataclass
import pandas as pd


@dataclass
class MarketContext:

    df: pd.DataFrame

    @property
    def latest(self):
        return self.df.iloc[-1]

    @property
    def history(self):
        return self.df
