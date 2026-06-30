import numpy as np
import pandas as pd


class VolatilityEngine:

    def compute_iv_rank(self, iv_series: pd.Series) -> float:
        """
        IV Rank = (current IV - min IV) / (max IV - min IV)
        """
        if len(iv_series) < 20:
            return 0.5

        current = iv_series.iloc[-1]
        low = iv_series.rolling(20).min().iloc[-1]
        high = iv_series.rolling(20).max().iloc[-1]

        if high == low:
            return 0.5

        return (current - low) / (high - low)

    def compute_expected_move(self, price: float, iv: float, days: int = 1) -> float:
        """
        Expected Move ≈ price × IV × sqrt(T)
        """
        return price * iv * np.sqrt(days / 365)

class VolatilityAnalyzer:

    def iv_rank(
        self,
        current_iv,
        low_iv,
        high_iv,
    ):
        return (
            current_iv - low_iv
        ) / (
            high_iv - low_iv
        )
