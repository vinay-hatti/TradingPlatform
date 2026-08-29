from datetime import date

from trading_ai.scanner.options_market_data_quality_analytics.contracts import (
    GovernanceStatus,
    ObservationStatus,
)
from trading_ai.scanner.options_market_data_quality_analytics.engine import (
    OptionChainQualityEngine,
    OptionContractQualityRow,
)


def make(symbol, *, bid=None, ask=None):
    return OptionContractQualityRow(
        underlying_symbol=symbol,
        quote_date=date(2026, 7, 20),
        bid=bid,
        ask=ask,
        last=1.5,
        volume=200,
        open_interest=200,
        implied_volatility=0.3,
        delta=0.5,
        gamma=0.02,
        theta=-0.03,
        vega=0.1,
    )


def main():
    # Entire provider run has no NBBO quotes.
    rows = [make("AAPL") for _ in range(20)]
    rows.extend(make("SMALL") for _ in range(5))

    profiles = OptionChainQualityEngine().evaluate(
        rows,
        quote_date=date(2026, 7, 20),
        expected_symbols=("AAPL", "SMALL", "NONE"),
    )

    aapl = next(p for p in profiles if p.symbol == "AAPL")
    small = next(p for p in profiles if p.symbol == "SMALL")
    none = next(p for p in profiles if p.symbol == "NONE")

    assert aapl.governance_status == GovernanceStatus.READY
    assert aapl.overall_quality_score == 1.0
    assert aapl.quote_observation_status == ObservationStatus.NOT_OBSERVED
    assert "NBBO" in aapl.informational_notes[0]

    assert small.governance_status == GovernanceStatus.REVIEW
    assert any("sparse chain" in reason for reason in small.governance_reasons)

    assert none.governance_status == GovernanceStatus.FAILED

    print(
        "Milestone 35 Phase 3 Step 4 provider-aware governance assertions passed."
    )


if __name__ == "__main__":
    main()
