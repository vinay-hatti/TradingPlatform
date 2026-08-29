from datetime import date

from trading_ai.scanner.options_market_data_coverage.contracts import (
    GovernanceStatus,
)
from trading_ai.scanner.options_market_data_coverage.engine import (
    OptionChainCoverageEngine,
    OptionContractCoverageRow,
)
from trading_ai.scanner.options_market_data_coverage.policy import (
    OptionChainCoveragePolicy,
)


def row(symbol, expiry, side, strike):
    return OptionContractCoverageRow(
        underlying_symbol=symbol,
        quote_date=date(2026, 7, 20),
        expiry=expiry,
        option_type=side,
        strike=strike,
    )


def main():
    expiry_1 = date(2026, 8, 21)
    expiry_2 = date(2026, 9, 18)

    rows = []
    for expiry in (expiry_1, expiry_2):
        for strike in (90, 95, 100, 105, 110):
            rows.append(row("AAPL", expiry, "CALL", strike))
            rows.append(row("AAPL", expiry, "PUT", strike))

    policy = OptionChainCoveragePolicy(
        minimum_contracts_per_symbol=20,
        minimum_expirations_per_symbol=2,
        minimum_strikes_per_expiration=5,
    )
    profiles = OptionChainCoverageEngine(policy).evaluate(
        rows,
        quote_date=date(2026, 7, 20),
        expected_symbols=("AAPL", "MSFT"),
    )

    aapl = next(item for item in profiles if item.symbol == "AAPL")
    msft = next(item for item in profiles if item.symbol == "MSFT")

    assert aapl.governance_status == GovernanceStatus.READY
    assert aapl.contract_count == 20
    assert aapl.expiration_count == 2
    assert aapl.call_put_balance_score == 1.0
    assert aapl.strike_surface_score == 1.0

    assert msft.governance_status == GovernanceStatus.FAILED
    assert msft.contract_count == 0

    print("Milestone 35 Phase 3 Step 3 engine assertions passed.")


if __name__ == "__main__":
    main()
