from datetime import date

from trading_ai.scanner.correlation_dispersion.engine import (
    CorrelationDispersionEngine,
)


def main():
    symbols = [
        "SPY", "QQQ", "IWM", "TLT", "HYG",
        "GLD", "UUP", "XLK",
    ]

    features = {}
    history = {}

    base = [0.001 if index % 2 == 0 else -0.001 for index in range(63)]

    for symbol_index, symbol in enumerate(symbols):
        long_history = [
            value * (1.0 + symbol_index * 0.01)
            for value in base
        ]
        recent = [
            value * (-1.0 if symbol_index % 2 else 1.0)
            for value in base[-21:]
        ]
        history[symbol] = long_history[:-21] + recent
        features[symbol] = {
            "symbol": symbol,
            "governance_status": "READY",
            "return_1d": history[symbol][-1],
            "return_5d": sum(history[symbol][-5:]),
            "return_21d": sum(history[symbol][-21:]),
        }

    profile = CorrelationDispersionEngine().evaluate(
        as_of_date=date(2026, 7, 20),
        features_by_symbol=features,
        return_history_by_symbol=history,
    )

    assert profile.correlation_breakdown_count > 0
    assert len(profile.breakdown_pairs) > 0

    print("Milestone 35 Phase 5 Step 4 breakdown assertions passed.")


if __name__ == "__main__":
    main()
