from trading_ai.indicators.ema import EMAIndicator
from trading_ai.indicators.rsi import RSIIndicator
from trading_ai.indicators.macd import MACDIndicator
from trading_ai.indicators.atr import ATRIndicator
from trading_ai.indicators.vwap import VWAPIndicator
from trading_ai.indicators.bollinger import BollingerBands


class IndicatorEngine:

    def __init__(self):

        self.indicators = [
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

    def run(self, df):

        for indicator in self.indicators:
            df = indicator.compute(df)

        return df
