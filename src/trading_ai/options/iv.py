import pandas as pd


class IVAnalyzer:

    def iv_rank(self, iv_series: pd.Series) -> float:
        """
        IV Rank = where current IV sits in historical range
        """
        return (
            (iv_series.iloc[-1] - iv_series.min()) / (iv_series.max() - iv_series.min())
        ) * 100
