import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.candidate_inspection_cli import run


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        input_path = root / "live_trade_candidates.json"
        output_dir = root / "candidate_inspection"

        input_path.write_text(
            json.dumps(
                {
                    "live_trade_candidates": [
                        {
                            "symbol": "AMZN",
                            "institutional_score": 91,
                            "probability_of_profit": 0.72,
                            "direction": "CALL",
                        },
                        {
                            "symbol": "LLY",
                            "institutional_score": 84,
                            "direction": "PUT",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

        return_code = run(
            [
                "--rankings-json",
                str(input_path),
                "--symbol",
                "AMZN",
                "--output-dir",
                str(output_dir),
                "--print-handoff-commands",
            ]
        )
        assert return_code == 0

        output_path = output_dir / "amzn_candidate_inspection.json"
        assert output_path.exists()

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["symbol"] == "AMZN"
        assert payload["institutional_score"] == 91.0
        assert payload["direction"] == "CALL"
        assert payload["option_chain_command"][-1] == "AMZN"

    print(
        "Milestone 35 Phase 5 Step 5 integration assertions passed."
    )


if __name__ == "__main__":
    main()
