from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from trading_ai.indicators._frame import normalize_market_frame
from trading_ai.indicators.atr import ATRIndicator
from trading_ai.indicators.bollinger import BollingerBands
from trading_ai.indicators.ema import EMAIndicator
from trading_ai.indicators.macd import MACDIndicator
from trading_ai.indicators.rsi import RSIIndicator
from trading_ai.indicators.vwap import VWAPIndicator


class IndicatorEngine:
    def __init__(self, indicators: Iterable[object] | None = None) -> None:
        self.indicators = list(
            indicators
            if indicators is not None
            else [
                EMAIndicator(8),
                EMAIndicator(21),
                EMAIndicator(50),
                EMAIndicator(200),
                RSIIndicator(14),
                MACDIndicator(),
                ATRIndicator(14),
                VWAPIndicator(),
                BollingerBands(20),
            ]
        )

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        result = normalize_market_frame(df)
        if result.empty:
            raise ValueError("IndicatorEngine received an empty DataFrame")

        for indicator in self.indicators:
            compute = getattr(indicator, "compute", None)
            if not callable(compute):
                raise TypeError(
                    f"{type(indicator).__name__} does not implement compute(df)"
                )
            result = compute(result)

        return result
