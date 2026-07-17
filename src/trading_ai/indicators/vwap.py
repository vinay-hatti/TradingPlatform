from __future__ import annotations

import pandas as pd

from trading_ai.indicators._frame import normalize_market_frame, require_columns


class VWAP:
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        result = normalize_market_frame(df)
        require_columns(result, "high", "low", "close", "volume")

        typical_price = (
            result["high"] + result["low"] + result["close"]
        ) / 3.0
        cumulative_volume = result["volume"].cumsum()
        result["vwap"] = (
            (typical_price * result["volume"]).cumsum()
            / cumulative_volume.replace(0.0, float("nan"))
        )
        return result


class VWAPIndicator(VWAP):
    """Explicit IndicatorEngine-compatible alias."""
