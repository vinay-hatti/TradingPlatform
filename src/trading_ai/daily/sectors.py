SECTOR_MAP = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "AMD": "Technology",
    "META": "Communication Services",
    "GOOGL": "Communication Services",
    "GOOG": "Communication Services",
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
    "SPY": "ETF",
    "QQQ": "ETF",
}


def sector_for(symbol):

    return SECTOR_MAP.get(
        str(symbol).upper(),
        "Unknown",
    )
