import math
import pandas as pd


class HistoricalVolatility:
    def calculate(self, df: pd.DataFrame, window: int = 20) -> float:
        if df is None or df.empty:
            return 0.0

        if "close" not in df.columns:
            return 0.0

        data = df.copy()
        data["return"] = data["close"].pct_change()

        hv = data["return"].rolling(window).std().iloc[-1]

        if pd.isna(hv):
            return 0.0

        return float(hv * math.sqrt(252))
