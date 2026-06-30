import numpy as np


class IVRankEngine:

    def __init__(self):
        self.history = {}

    def compute(self, symbol, iv_series):
        """
        iv_series: list[float] or pd.Series
        """

        iv = np.array(iv_series, dtype=float)

        if len(iv) < 20:
            return {
                "iv_rank": 0.5,
                "iv_percentile": 0.5,
            }

        low = np.min(iv[-252:])   # 1-year low
        high = np.max(iv[-252:])  # 1-year high
        current = iv[-1]

        if high == low:
            rank = 0.5
        else:
            rank = (current - low) / (high - low)

        percentile = np.mean(iv <= current)

        return {
            "iv_rank": float(rank),
            "iv_percentile": float(percentile),
        }
