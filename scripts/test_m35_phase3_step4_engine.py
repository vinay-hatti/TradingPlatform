from datetime import date

from trading_ai.scanner.options_market_data_quality_analytics.contracts import (
    GovernanceStatus,
)
from trading_ai.scanner.options_market_data_quality_analytics.engine import (
    OptionChainQualityEngine,
    OptionContractQualityRow,
)
from trading_ai.scanner.options_market_data_quality_analytics.policy import (
    OptionChainQualityPolicy,
)


def row(symbol, *, bid=1.0, ask=1.2, last=1.1, volume=200, oi=300):
    return OptionContractQualityRow(
        underlying_symbol=symbol,
        quote_date=date(2026, 7, 20),
        bid=bid,
        ask=ask,
        last=last,
        volume=volume,
        open_interest=oi,
        implied_volatility=0.30,
        delta=0.50,
        gamma=0.02,
        theta=-0.04,
        vega=0.10,
    )


def main():
    rows = [row("AAPL") for _ in range(20)]
    rows.extend(
        [
            row("BAD", bid=None, ask=None, last=None, volume=0, oi=0)
            for _ in range(10)
        ]
    )

    profiles = OptionChainQualityEngine(
        OptionChainQualityPolicy()
    ).evaluate(
        rows,
        quote_date=date(2026, 7, 20),
        expected_symbols=("AAPL", "BAD", "MSFT"),
    )

    aapl = next(item for item in profiles if item.symbol == "AAPL")
    bad = next(item for item in profiles if item.symbol == "BAD")
    msft = next(item for item in profiles if item.symbol == "MSFT")

    assert aapl.governance_status == GovernanceStatus.READY
    assert aapl.quote_completeness_score == 1.0
    assert aapl.liquidity_score == 1.0
    assert aapl.greeks_completeness_score == 1.0

    assert bad.governance_status == GovernanceStatus.FAILED
    assert msft.governance_status == GovernanceStatus.FAILED

    print("Milestone 35 Phase 3 Step 4 engine assertions passed.")


if __name__ == "__main__":
    main()
