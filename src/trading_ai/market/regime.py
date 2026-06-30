import numpy as np


class MarketRegimeEngine:

    def classify(self, df):

        last_close = df["close"].iloc[-1]
        ema200 = df["ema200"].iloc[-1]
        rsi = df["rsi14"].iloc[-1]
        atr = df["atr14"].iloc[-1]

        volatility = df["close"].pct_change().std()

        if last_close > ema200 and rsi > 55:
            regime = "BULL_TREND"
        elif last_close < ema200 and rsi < 45:
            regime = "BEAR_TREND"
        elif volatility > 0.02:
            regime = "HIGH_VOLATILITY"
        else:
            regime = "CHOP"

        return regime
