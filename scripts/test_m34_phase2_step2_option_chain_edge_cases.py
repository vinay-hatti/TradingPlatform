from datetime import date

from trading_ai.research_workstation.analysis import (
    OptionChainExplorerEngine,
)


def main() -> None:
    empty = OptionChainExplorerEngine().analyze(
        symbol="EMPTY",
        underlying_price=100.0,
        contracts=[],
        quote_date=date(2026, 7, 19),
    )
    assert empty.contract_count == 0
    assert empty.expiration_count == 0
    assert empty.preferred_expiration is None
    assert "No option contracts were supplied" in empty.warnings

    weak = OptionChainExplorerEngine().analyze(
        symbol="WEAK",
        underlying_price=100.0,
        quote_date=date(2026, 7, 19),
        contracts=[
            {
                "expiry": "2026-08-21",
                "strike": 120,
                "option_type": "CALL",
                "bid": 0.05,
                "ask": 0.25,
                "volume": 0,
                "open_interest": 10,
                "implied_volatility": 0.60,
                "delta": 0.10,
            }
        ],
    )
    item = weak.contracts[0]
    assert item.liquidity_grade == "D"
    assert "Option volume below policy minimum" in item.warnings
    assert "Open interest below policy minimum" in item.warnings
    assert "Bid/ask spread exceeds policy maximum" in item.warnings

    print(
        "Milestone 34 Phase 2 Step 2 edge-case assertions passed."
    )


if __name__ == "__main__":
    main()
