from trading_ai.indicators.ema import EMA
from trading_ai.indicators.rsi import RSI
from trading_ai.indicators.macd import MACD
from trading_ai.indicators.atr import ATR


class FeatureEngine:

    def build_features(self, df):

        #        df.columns = [c.lower() for c in df.columns]

        df["ema20"] = EMA(20).calculate(df["close"])
        df["ema50"] = EMA(50).calculate(df["close"])
        df["ema200"] = EMA(200).calculate(df["close"])

        df["rsi14"] = RSI(14).calculate(df["close"])

        macd = MACD().calculate(df["close"])
        df["macd"] = macd["macd"]
        df["macd_signal"] = macd["signal"]

        df["atr14"] = ATR(14).calculate(df)

        return df
