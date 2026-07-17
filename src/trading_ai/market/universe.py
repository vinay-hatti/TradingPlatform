from __future__ import annotations

"""
Shared equity universes used by ingestion and trade scanning.

SP500_TOP_100 is an intentionally stable, liquid, large-cap subset of the
S&P 500. It contains exactly 100 unique ticker symbols and is used as the
default local scanning universe.

The ordering is approximate large-cap priority, not a live index-weight
calculation. Use explicit --symbols when an exact custom universe is needed.
"""

SP500_TOP_100: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "AVGO",
    "TSLA",
    "BRK.B",
    "LLY",
    "JPM",
    "WMT",
    "V",
    "ORCL",
    "MA",
    "XOM",
    "COST",
    "JNJ",
    "NFLX",
    "HD",
    "PG",
    "ABBV",
    "BAC",
    "KO",
    "PLTR",
    "CRM",
    "UNH",
    "CSCO",
    "PM",
    "IBM",
    "CVX",
    "GE",
    "WFC",
    "ABT",
    "MCD",
    "CAT",
    "MRK",
    "AXP",
    "NOW",
    "TMO",
    "GS",
    "ISRG",
    "DIS",
    "PEP",
    "QCOM",
    "INTU",
    "RTX",
    "UBER",
    "AMGN",
    "BKNG",
    "TXN",
    "AMD",
    "ACN",
    "SPGI",
    "PGR",
    "BLK",
    "NEE",
    "DHR",
    "LOW",
    "AMAT",
    "ETN",
    "HON",
    "PFE",
    "C",
    "TJX",
    "VRTX",
    "SYK",
    "BSX",
    "ADP",
    "SCHW",
    "PANW",
    "GILD",
    "ADI",
    "DE",
    "CB",
    "LRCX",
    "MU",
    "MMC",
    "MDT",
    "COP",
    "AMT",
    "CRWD",
    "MO",
    "SO",
    "KLAC",
    "DUK",
    "SHW",
    "ICE",
    "CEG",
    "CME",
    "CMCSA",
    "USB",
    "MCK",
    "WM",
    "APH",
    "NKE",
    "ORLY",
    "MAR",
    "GD",
    "SBUX",
)

# Backward-compatible alias used by existing ingestion code.
SP500 = list(SP500_TOP_100)


def get_universe(name: str = "sp500-top100") -> tuple[str, ...]:
    normalized = name.strip().lower().replace("_", "-")
    if normalized in {
        "sp500-top100",
        "sp500",
        "top100",
        "top-100",
        "large-cap-100",
    }:
        return SP500_TOP_100
    raise ValueError(
        f"Unsupported universe '{name}'. Supported: sp500-top100"
    )


def validate_universe(symbols: tuple[str, ...]) -> None:
    if len(symbols) != 100:
        raise ValueError(
            f"SP500_TOP_100 must contain exactly 100 symbols; got {len(symbols)}"
        )
    if len(set(symbols)) != len(symbols):
        raise ValueError("SP500_TOP_100 contains duplicate symbols")
    invalid = [
        symbol
        for symbol in symbols
        if not symbol or symbol != symbol.upper() or " " in symbol
    ]
    if invalid:
        raise ValueError(f"Invalid symbols in SP500_TOP_100: {invalid}")


validate_universe(SP500_TOP_100)
