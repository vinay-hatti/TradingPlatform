import pandas as pd


class EMA:

    def __init__(self, period: int):
        self.period = period

    def calculate(self, series: pd.Series) -> pd.Series:
        return series.ewm(span=self.period, adjust=False).mean()
