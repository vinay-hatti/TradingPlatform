from .contracts import AssetClass, CrossAssetUniverseMember

def default_cross_asset_universe() -> tuple[CrossAssetUniverseMember, ...]:
    raw = [
        ("SPY", AssetClass.EQUITY_INDEX, "US_LARGE_CAP", None),
        ("QQQ", AssetClass.EQUITY_INDEX, "US_GROWTH", "SPY"),
        ("IWM", AssetClass.EQUITY_INDEX, "US_SMALL_CAP", "SPY"),
        ("DIA", AssetClass.EQUITY_INDEX, "US_BLUE_CHIP", "SPY"),
        ("^VIX", AssetClass.VOLATILITY, "IMPLIED_VOLATILITY", None),
        ("VXX", AssetClass.VOLATILITY, "VOLATILITY_ETP", "^VIX"),
        ("VIXY", AssetClass.VOLATILITY, "VOLATILITY_ETP", "^VIX"),
        ("SHY", AssetClass.TREASURY, "SHORT_DURATION", "IEF"),
        ("IEI", AssetClass.TREASURY, "INTERMEDIATE_SHORT", "IEF"),
        ("IEF", AssetClass.TREASURY, "INTERMEDIATE", None),
        ("TLT", AssetClass.TREASURY, "LONG_DURATION", "IEF"),
        ("LQD", AssetClass.CREDIT, "INVESTMENT_GRADE", "IEF"),
        ("HYG", AssetClass.CREDIT, "HIGH_YIELD", "LQD"),
        ("GLD", AssetClass.COMMODITY, "GOLD", "SPY"),
        ("SLV", AssetClass.COMMODITY, "SILVER", "GLD"),
        ("USO", AssetClass.COMMODITY, "CRUDE_OIL", "SPY"),
        ("UUP", AssetClass.CURRENCY, "US_DOLLAR", "SPY"),
        ("XLF", AssetClass.SECTOR, "FINANCIALS", "SPY"),
        ("XLK", AssetClass.SECTOR, "TECHNOLOGY", "SPY"),
        ("XLE", AssetClass.SECTOR, "ENERGY", "SPY"),
        ("XLI", AssetClass.SECTOR, "INDUSTRIALS", "SPY"),
        ("XLV", AssetClass.SECTOR, "HEALTH_CARE", "SPY"),
        ("XLY", AssetClass.SECTOR, "CONSUMER_DISCRETIONARY", "SPY"),
        ("XLP", AssetClass.SECTOR, "CONSUMER_STAPLES", "SPY"),
        ("XLU", AssetClass.SECTOR, "UTILITIES", "SPY"),
        ("XLB", AssetClass.SECTOR, "MATERIALS", "SPY"),
        ("XLRE", AssetClass.SECTOR, "REAL_ESTATE", "SPY"),
        ("XLC", AssetClass.SECTOR, "COMMUNICATION_SERVICES", "SPY"),
    ]
    return tuple(CrossAssetUniverseMember(*row) for row in raw)
