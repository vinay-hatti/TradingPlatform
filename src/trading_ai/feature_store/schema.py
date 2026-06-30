REQUIRED_COLUMNS = [
    "symbol",
    "time",
    "open",
    "high",
    "low",
    "close",
    "volume",
]


def validate_market_df(df):
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return df
