import numpy as np
import pandas as pd


class OptionsFeatureEngine:

    def compute_hv(self, df: pd.DataFrame, window: int = 20) -> pd.Series:
        """
        Historical volatility (annualized)
        """
        returns = df["close"].pct_change()

        hv = returns.rolling(window).std() * np.sqrt(252)
        return hv

    def expected_move(self, price: float, hv: float, days: int = 1) -> float:
        """
        Expected move using volatility approximation:
        Move ≈ price * hv * sqrt(T)
        """
        return price * hv * np.sqrt(days / 252)

    def iv_rank_proxy(self, hv: float, hv_min: float, hv_max: float) -> float:
        """
        IV Rank approximation using historical volatility range
        """
        if hv_max - hv_min == 0:
            return 0.5

        return (hv - hv_min) / (hv_max - hv_min)
