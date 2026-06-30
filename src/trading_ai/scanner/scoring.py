import pandas as pd


class ScannerScoring:

    def score(self, df: pd.DataFrame) -> float:

        score = 0

        # Trend strength
        if df["ema_8"].iloc[-1] > df["ema_21"].iloc[-1]:
            score += 20
        if df["ema_21"].iloc[-1] > df["ema_50"].iloc[-1]:
            score += 20

        # Momentum
        if df["rsi"].iloc[-1] > 60:
            score += 15
        if df["macd_hist"].iloc[-1] > 0:
            score += 15

        # Volatility squeeze (lower ATR = compression)
        atr_ratio = df["atr"].iloc[-1] / df["atr"].rolling(20).mean().iloc[-1]
        if atr_ratio < 0.8:
            score += 20

        # Breakout proximity (Bollinger squeeze)
        price = df["Close"].iloc[-1]
        if price < df["bb_upper"].iloc[-1]:
            score += 10

        # Volume confirmation
        if df["Volume"].iloc[-1] > df["Volume"].rolling(20).mean().iloc[-1]:
            score += 10

        return score
