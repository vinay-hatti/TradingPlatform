from __future__ import annotations

import pandas as pd

from trading_ai.indicators._frame import normalize_market_frame, require_columns


class ATR:
    """Legacy DataFrame-level average true range calculator."""

    def __init__(self, period: int = 14) -> None:
        if period <= 0:
            raise ValueError("period must be positive")
        self.period = period

    def calculate(self, df: pd.DataFrame) -> pd.Series:
        result = normalize_market_frame(df)
        require_columns(result, "high", "low", "close")

        high = result["high"]
        low = result["low"]
        close = result["close"]

        true_range = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)

        return true_range.ewm(
            alpha=1 / self.period,
            min_periods=self.period,
            adjust=False,
        ).mean()


class ATRIndicator(ATR):
    def __init__(
        self,
        period: int = 14,
        output_column: str | None = None,
    ) -> None:
        super().__init__(period)
        self.output_column = output_column or f"atr_{period}"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        result = normalize_market_frame(df)
        result[self.output_column] = self.calculate(result)
        return result
