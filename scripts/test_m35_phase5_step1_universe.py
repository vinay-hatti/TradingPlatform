from trading_ai.scanner.cross_asset_data_foundation.universe import default_cross_asset_universe

def main():
    u = default_cross_asset_universe()
    symbols = {m.symbol for m in u}
    for symbol in ("SPY", "QQQ", "TLT", "HYG", "GLD", "UUP", "XLK", "XLP"):
        assert symbol in symbols
    assert len(symbols) == len(u)
    print("Milestone 35 Phase 5 Step 1 universe assertions passed.")

if __name__ == "__main__":
    main()
