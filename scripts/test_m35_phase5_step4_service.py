import json
import tempfile
from datetime import date
from math import sin
from pathlib import Path

from trading_ai.scanner.correlation_dispersion.service import (
    CorrelationDispersionService,
)


def main():
    symbols = [
        "SPY", "QQQ", "IWM", "TLT", "HYG",
        "GLD", "UUP", "XLK", "XLP",
    ]

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        feature_path = root / "features.jsonl"
        history_path = root / "history.jsonl"
        output_path = root / "profile.json"

        with feature_path.open("w", encoding="utf-8") as feature_handle,              history_path.open("w", encoding="utf-8") as history_handle:
            for index, symbol in enumerate(symbols):
                returns = [
                    0.001 * sin(day / 4.0 + index * 0.4)
                    for day in range(90)
                ]
                feature_handle.write(
                    json.dumps(
                        {
                            "symbol": symbol,
                            "governance_status": "READY",
                            "return_1d": returns[-1],
                            "return_5d": sum(returns[-5:]),
                            "return_21d": sum(returns[-21:]),
                        }
                    )
                    + "\n"
                )
                history_handle.write(
                    json.dumps(
                        {
                            "symbol": symbol,
                            "returns": returns,
                        }
                    )
                    + "\n"
                )

        run_profile = CorrelationDispersionService().run(
            as_of_date=date(2026, 7, 20),
            input_path=feature_path,
            history_path=history_path,
            output_path=output_path,
        )

        assert output_path.exists()
        assert run_profile.records_read == 9
        assert run_profile.symbols_available == 9
        assert run_profile.pair_count == 36
        assert run_profile.correlation_regime
        assert run_profile.dispersion_regime
        assert run_profile.market_structure_state

    print("Milestone 35 Phase 5 Step 4 service assertions passed.")


if __name__ == "__main__":
    main()
