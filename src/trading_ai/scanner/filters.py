import pandas as pd


class ScannerFilters:

    def trend_filter(self, df: pd.DataFrame) -> bool:
        """
        Bullish trend: EMA8 > EMA21 > EMA50
        """
        return df["ema_8"].iloc[-1] > df["ema_21"].iloc[-1] > df["ema_50"].iloc[-1]

    def momentum_filter(self, df: pd.DataFrame) -> bool:
        """
        Momentum confirmation
        """
        return (
            df["rsi"].iloc[-1] > 50 and df["macd"].iloc[-1] > df["macd_signal"].iloc[-1]
        )

    def volatility_filter(self, df: pd.DataFrame) -> bool:
        """
        Volatility compression (pre-breakout setup)
        """
        recent_atr = df["atr"].iloc[-1]
        atr_mean = df["atr"].rolling(20).mean().iloc[-1]

        return recent_atr < atr_mean
