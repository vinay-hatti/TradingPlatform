from __future__ import annotations

import pandas as pd

from trading_ai.indicators._frame import normalize_market_frame, require_columns


class RSI:
    """Legacy series-level RSI calculator."""

    def __init__(self, period: int = 14) -> None:
        if period <= 0:
            raise ValueError("period must be positive")
        self.period = period

    def calculate(self, series: pd.Series) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)

        average_gain = gain.ewm(
            alpha=1 / self.period,
            min_periods=self.period,
            adjust=False,
        ).mean()
        average_loss = loss.ewm(
            alpha=1 / self.period,
            min_periods=self.period,
            adjust=False,
        ).mean()

        relative_strength = average_gain / average_loss.replace(0.0, float("nan"))
        rsi = 100.0 - (100.0 / (1.0 + relative_strength))

        no_loss = average_loss.eq(0.0) & average_gain.gt(0.0)
        no_gain_or_loss = average_loss.eq(0.0) & average_gain.eq(0.0)
        rsi = rsi.mask(no_loss, 100.0)
        rsi = rsi.mask(no_gain_or_loss, 50.0)
        return rsi


class RSIIndicator(RSI):
    def __init__(
        self,
        period: int = 14,
        source_column: str = "close",
        output_column: str | None = None,
    ) -> None:
        super().__init__(period)
        self.source_column = source_column.lower()
        self.output_column = output_column or f"rsi_{period}"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        result = normalize_market_frame(df)
        require_columns(result, self.source_column)
        result[self.output_column] = self.calculate(result[self.source_column])
        return result
