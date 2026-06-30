import pandas as pd


class VWAP:

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:

        tp = (df["High"] + df["Low"] + df["Close"]) / 3

        df["vwap"] = (tp * df["Volume"]).cumsum() / df["Volume"].cumsum()

        return df
