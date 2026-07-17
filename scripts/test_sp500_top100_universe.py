from __future__ import annotations

import argparse

from trading_ai.market.universe import (
    SP500,
    SP500_TOP_100,
    get_universe,
    validate_universe,
)


def main() -> None:
    validate_universe(SP500_TOP_100)

    assert len(SP500_TOP_100) == 100
    assert len(set(SP500_TOP_100)) == 100
    assert tuple(SP500) == SP500_TOP_100
    assert get_universe("sp500-top100") == SP500_TOP_100
    assert get_universe("top100") == SP500_TOP_100

    args = argparse.Namespace(
        symbols=None,
        universe="sp500-top100",
    )

    # Import after universe validation so failures clearly identify the source.
    from run_daily_scan import resolve_symbols

    resolved = resolve_symbols(args)
    assert len(resolved) == 100
    assert resolved[0] == "AAPL"
    assert resolved[-1] == "SBUX"

    custom = argparse.Namespace(
        symbols="AAPL, MSFT, AAPL",
        universe="sp500-top100",
    )
    assert resolve_symbols(custom) == ["AAPL", "MSFT"]

    print("All S&P 500 top-100 universe assertions passed.")


if __name__ == "__main__":
    main()
