import pandas as pd


class BollingerBands:

    def __init__(self, period: int = 20):
        self.period = period

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:

        mid = df["Close"].rolling(self.period).mean()
        std = df["Close"].rolling(self.period).std()

        df["bb_mid"] = mid
        df["bb_upper"] = mid + 2 * std
        df["bb_lower"] = mid - 2 * std

        return df
