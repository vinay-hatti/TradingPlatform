from __future__ import annotations

import pandas as pd

from trading_ai.indicators._frame import normalize_market_frame, require_columns


class MACD:
    """Legacy series-level MACD calculator."""

    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> None:
        if min(fast, slow, signal) <= 0:
            raise ValueError("MACD periods must be positive")
        if fast >= slow:
            raise ValueError("fast period must be smaller than slow period")
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def calculate(self, series: pd.Series) -> dict[str, pd.Series]:
        ema_fast = series.ewm(span=self.fast, adjust=False).mean()
        ema_slow = series.ewm(span=self.slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=self.signal, adjust=False).mean()
        return {
            "macd": macd,
            "signal": signal_line,
            "histogram": macd - signal_line,
        }


class MACDIndicator(MACD):
    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        source_column: str = "close",
    ) -> None:
        super().__init__(fast=fast, slow=slow, signal=signal)
        self.source_column = source_column.lower()

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        result = normalize_market_frame(df)
        require_columns(result, self.source_column)
        values = self.calculate(result[self.source_column])
        result["macd"] = values["macd"]
        result["macd_signal"] = values["signal"]
        result["macd_histogram"] = values["histogram"]
        return result
