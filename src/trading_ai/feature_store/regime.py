import pandas as pd


class RegimeEngine:

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:

        df = df.copy()

        # Default
        df["market_regime"] = "CHOP"

        # Trend regime
        if {"ema20", "ema50"}.issubset(df.columns):

            df.loc[df["ema20"] > df["ema50"], "market_regime"] = "BULL_TREND"
            df.loc[df["ema20"] < df["ema50"], "market_regime"] = "BEAR_TREND"

        # Volatility regime
        if "atr14" in df.columns:

            atr_mean = df["atr14"].rolling(20).mean().fillna(df["atr14"])

            price_change = df["close"].pct_change().abs().fillna(0)

            df.loc[
                (df["atr14"] > atr_mean) & (price_change > 0.02),
                "market_regime",
            ] = "VOLATILE"

        return df
