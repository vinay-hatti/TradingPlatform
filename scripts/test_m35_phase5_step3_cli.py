import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.ranking_cli import run
from trading_ai.scanner.dashboard.ranking_loader import load_ranking_records


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        input_path = root / "rankings.json"
        output_dir = root / "output"
        input_path.write_text(
            json.dumps(
                {
                    "rankings": [
                        {
                            "symbol": "AAPL",
                            "rank": 1,
                            "institutional_score": 0.95,
                            "probability_score": 0.78,
                            "sector": "Technology",
                            "regime": "TREND_UP",
                        },
                        {
                            "symbol": "MSFT",
                            "rank": 2,
                            "institutional_score": 0.91,
                            "probability": 0.74,
                            "sector": "Technology",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

        records = load_ranking_records(input_path)
        assert [record.symbol for record in records] == ["AAPL", "MSFT"]

        result = run(
            [
                "--rankings-json",
                str(input_path),
                "--output-dir",
                str(output_dir),
                "--top-n",
                "50",
                "--page-size",
                "25",
                "--sort-field",
                "institutional_score",
                "--sort-direction",
                "DESC",
                "--search",
                "technology",
                "--select-symbol",
                "AAPL",
            ]
        )
        assert result == 0
        assert (output_dir / "opportunity_rankings_view.json").exists()
        assert (output_dir / "opportunity_rankings.html").exists()

    print("Milestone 35 Phase 5 Step 3 CLI assertions passed.")


if __name__ == "__main__":
    main()
