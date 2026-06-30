import pandas as pd


class RSI:

    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, series: pd.Series) -> pd.Series:

        delta = series.diff()

        gain = delta.where(delta > 0, 0).rolling(self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.period).mean()

        rs = gain / loss.replace(0, 1e-9)
        return 100 - (100 / (1 + rs))
