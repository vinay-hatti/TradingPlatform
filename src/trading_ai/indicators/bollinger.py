from __future__ import annotations

import pandas as pd

from trading_ai.indicators._frame import normalize_market_frame, require_columns


class BollingerBands:
    def __init__(
        self,
        period: int = 20,
        standard_deviations: float = 2.0,
    ) -> None:
        if period <= 0:
            raise ValueError("period must be positive")
        if standard_deviations <= 0:
            raise ValueError("standard_deviations must be positive")
        self.period = period
        self.standard_deviations = standard_deviations

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        result = normalize_market_frame(df)
        require_columns(result, "close")

        middle = result["close"].rolling(
            self.period,
            min_periods=self.period,
        ).mean()
        deviation = result["close"].rolling(
            self.period,
            min_periods=self.period,
        ).std()

        result["bb_mid"] = middle
        result["bb_upper"] = middle + self.standard_deviations * deviation
        result["bb_lower"] = middle - self.standard_deviations * deviation
        return result
