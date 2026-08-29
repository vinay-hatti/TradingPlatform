import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.strategy_comparison_cli import run


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        chain_path = root / "amzn_option_chain_inspection.json"
        output_dir = root / "strategy_comparison"

        chain_path.write_text(
            json.dumps(
                {
                    "symbol": "AMZN",
                    "quote_policy": "STRICT",
                    "calls": [
                        {
                            "symbol": "AMZN",
                            "expiry": "2026-08-21",
                            "strike": 215,
                            "option_type": "CALL",
                            "bid": 8.0,
                            "ask": 8.4,
                            "last": 8.2,
                            "volume": 900,
                            "open_interest": 3000,
                            "delta": 0.62,
                        },
                        {
                            "symbol": "AMZN",
                            "expiry": "2026-08-21",
                            "strike": 220,
                            "option_type": "CALL",
                            "bid": 5.0,
                            "ask": 5.4,
                            "last": 5.2,
                            "volume": 800,
                            "open_interest": 2500,
                            "delta": 0.54,
                        },
                    ],
                    "puts": [],
                }
            ),
            encoding="utf-8",
        )

        code = run(
            [
                "--option-chain-json",
                str(chain_path),
                "--direction",
                "CALL",
                "--output-dir",
                str(output_dir),
            ]
        )
        assert code == 0

        output_path = (
            output_dir / "amzn_call_strategy_comparison.json"
        )
        assert output_path.exists()
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["symbol"] == "AMZN"
        assert payload["generated_strategies"] == 3
        assert len(payload["ranked_strategies"]) == 3

    print(
        "Milestone 35 Phase 5 Step 7 integration assertions passed."
    )


if __name__ == "__main__":
    main()
