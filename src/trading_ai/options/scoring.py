import numpy as np


class OptionsScoringEngine:

    def __init__(self, iv_provider=None):
        self.iv_provider = iv_provider

    def score_long_call(self, row) -> float:

        score = 0

        if row["close"] > row["ema50"] > row["ema200"]:
            score += 25
        elif row["close"] > row["ema200"]:
            score += 15

        if row["rsi14"] > 55:
            score += 20
        elif row["rsi14"] > 50:
            score += 10

        if row["atr14"] > row["atr14_mean"]:
            score += 15

        if row["market_regime"] == "BULL_TREND":
            score += 20
        elif row["market_regime"] == "CHOP":
            score -= 10

        if hasattr(row, "iv_rank"):
            if row["iv_rank"] < 0.3:
               score += 10
            elif row["iv_rank"] > 0.8:
               score -= 10

        return max(0, min(100, score))

    def score_long_put(self, row) -> float:

        score = 0

        if row["close"] < row["ema50"] < row["ema200"]:
            score += 25
        elif row["close"] < row["ema200"]:
            score += 15

        if row["rsi14"] < 45:
            score += 20
        elif row["rsi14"] < 50:
            score += 10

        if row["market_regime"] == "BEAR_TREND":
            score += 20
        elif row["market_regime"] == "CHOP":
            score -= 10

        if "iv_rank" in row:
            if row["iv_rank"] < 0.3:
                score += 10
            elif row["iv_rank"] > 0.8:
                score -= 10

        return max(0, min(100, score))
