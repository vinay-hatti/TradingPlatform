import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.option_chain_cli import run


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        chain_path = root / "chain.csv"
        output_dir = root / "output"

        with chain_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "underlying_symbol",
                    "expiry",
                    "strike",
                    "option_type",
                    "bid",
                    "ask",
                    "volume",
                    "open_interest",
                ],
            )
            writer.writeheader()
            writer.writerows(
                [
                    {
                        "underlying_symbol": "AMZN",
                        "expiry": "2026-08-21",
                        "strike": 220,
                        "option_type": "CALL",
                        "bid": 5.0,
                        "ask": 5.4,
                        "volume": 800,
                        "open_interest": 2500,
                    },
                    {
                        "underlying_symbol": "LLY",
                        "expiry": "2026-08-21",
                        "strike": 700,
                        "option_type": "PUT",
                        "bid": 8.0,
                        "ask": 10.0,
                        "volume": 10,
                        "open_interest": 20,
                    },
                ]
            )

        code = run(
            [
                "--option-chain-file",
                str(chain_path),
                "--symbol",
                "AMZN",
                "--min-volume",
                "100",
                "--min-open-interest",
                "500",
                "--max-spread-pct",
                "0.20",
                "--output-dir",
                str(output_dir),
            ]
        )
        assert code == 0

        output_path = (
            output_dir / "amzn_option_chain_inspection.json"
        )
        assert output_path.exists()
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["symbol"] == "AMZN"
        assert payload["filtered_contracts"] == 1
        assert len(payload["calls"]) == 1

    print(
        "Milestone 35 Phase 5 Step 6 integration assertions passed."
    )


if __name__ == "__main__":
    main()
