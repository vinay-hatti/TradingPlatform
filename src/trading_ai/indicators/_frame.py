from __future__ import annotations

import pandas as pd


def normalize_market_frame(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a copy with flat, lower-case market-data columns.

    Handles yfinance single-symbol MultiIndex columns as well as ordinary
    DataFrames. Required OHLCV names become open/high/low/close/volume.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame")

    result = df.copy()

    if isinstance(result.columns, pd.MultiIndex):
        # yfinance commonly returns (field, ticker) for a single symbol.
        first_level = result.columns.get_level_values(0)
        second_level = result.columns.get_level_values(1)

        known = {"open", "high", "low", "close", "adj close", "volume", "date"}
        first_known = sum(str(value).strip().lower() in known for value in first_level)
        second_known = sum(str(value).strip().lower() in known for value in second_level)

        selected = first_level if first_known >= second_known else second_level
        result.columns = [str(value) for value in selected]

    result.columns = [
        str(column).strip().lower().replace(" ", "_")
        for column in result.columns
    ]

    if "adj_close" in result.columns and "close" not in result.columns:
        result = result.rename(columns={"adj_close": "close"})

    return result


def require_columns(df: pd.DataFrame, *columns: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(
            "Market data is missing required column(s): "
            + ", ".join(missing)
            + f". Available columns: {list(df.columns)}"
        )
