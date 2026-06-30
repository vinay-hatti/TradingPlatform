import pandas as pd


class MACD:

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def calculate(self, series: pd.Series) -> dict:

        ema_fast = series.ewm(span=self.fast, adjust=False).mean()
        ema_slow = series.ewm(span=self.slow, adjust=False).mean()

        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=self.signal, adjust=False).mean()

        return {
            "macd": macd,
            "signal": signal_line,
        }
