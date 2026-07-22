from datetime import date
from math import sin

from trading_ai.scanner.correlation_dispersion.contracts import (
    CorrelationDispersionGovernanceStatus,
)
from trading_ai.scanner.correlation_dispersion.engine import (
    CorrelationDispersionEngine,
)


def main():
    symbols = [
        "SPY", "QQQ", "IWM", "TLT", "HYG",
        "GLD", "UUP", "XLK", "XLP",
    ]

    features = {}
    history = {}

    for index, symbol in enumerate(symbols):
        returns = [
            0.001 * sin(day / 3.0 + index * 0.5)
            + 0.0002 * index
            for day in range(90)
        ]
        history[symbol] = returns
        features[symbol] = {
            "symbol": symbol,
            "governance_status": "READY",
            "return_1d": returns[-1],
            "return_5d": sum(returns[-5:]),
            "return_21d": sum(returns[-21:]),
        }

    profile = CorrelationDispersionEngine().evaluate(
        as_of_date=date(2026, 7, 20),
        features_by_symbol=features,
        return_history_by_symbol=history,
    )

    assert (
        profile.governance_status
        in {
            CorrelationDispersionGovernanceStatus.READY,
            CorrelationDispersionGovernanceStatus.REVIEW,
        }
    )
    assert profile.governed_symbol_count == 9
    assert profile.pair_count == 36
    assert profile.average_absolute_correlation_21d is not None
    assert profile.cross_sectional_dispersion_21d is not None
    assert 0.0 <= profile.diversification_score <= 1.0
    assert profile.correlation_regime
    assert profile.dispersion_regime
    assert profile.market_structure_state
    assert len(profile.pair_profiles) == 36

    print("Milestone 35 Phase 5 Step 4 engine assertions passed.")


if __name__ == "__main__":
    main()
