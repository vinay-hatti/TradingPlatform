import pandas as pd


def ensure_columns(df: pd.DataFrame, cols: list[str]):
    for c in cols:
        if c not in df.columns:
            df[c] = 0
    return df
