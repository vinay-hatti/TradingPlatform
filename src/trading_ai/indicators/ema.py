from __future__ import annotations

import pandas as pd

from trading_ai.indicators._frame import normalize_market_frame, require_columns


class EMA:
    """Legacy series-level exponential moving average calculator."""

    def __init__(self, period: int) -> None:
        if period <= 0:
            raise ValueError("period must be positive")
        self.period = period

    def calculate(self, series: pd.Series) -> pd.Series:
        return series.ewm(span=self.period, adjust=False).mean()


class EMAIndicator(EMA):
    """DataFrame indicator contract used by IndicatorEngine."""

    def __init__(
        self,
        period: int,
        source_column: str = "close",
        output_column: str | None = None,
    ) -> None:
        super().__init__(period)
        self.source_column = source_column.lower()
        self.output_column = output_column or f"ema_{period}"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        result = normalize_market_frame(df)
        require_columns(result, self.source_column)
        result[self.output_column] = self.calculate(result[self.source_column])
        return result
