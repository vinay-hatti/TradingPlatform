from trading_ai.database.models import PriceHistory
from trading_ai.research_workstation.scanner.market_data_adapter import (
    MarketBarProfile,
    PriceHistoryMarketDataAdapter,
)


def main() -> None:
    assert PriceHistory is not None
    assert MarketBarProfile is not None
    assert PriceHistoryMarketDataAdapter is not None

    adapter = PriceHistoryMarketDataAdapter
    assert hasattr(adapter, "load_bars")

    print("Milestone 34 Phase 1 Step 2 model import compatibility passed.")


if __name__ == "__main__":
    main()
