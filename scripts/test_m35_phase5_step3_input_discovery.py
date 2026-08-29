import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.ranking_loader import (
    discover_ranking_files,
    load_ranking_records,
    resolve_ranking_path,
)


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        report_dir = root / "reports" / "m35" / "phase3"
        report_dir.mkdir(parents=True)

        ranking_path = report_dir / "opportunity_rankings.json"
        ranking_path.write_text(
            json.dumps(
                {
                    "rankings": [
                        {
                            "symbol": "AAPL",
                            "institutional_score": 0.92,
                            "probability_score": 0.77,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        discovered = discover_ranking_files((root / "reports",))
        assert discovered == [ranking_path]

        resolved = resolve_ranking_path(ranking_path)
        assert resolved == ranking_path

        loaded_path, records = load_ranking_records(ranking_path)
        assert loaded_path == ranking_path
        assert records[0].symbol == "AAPL"

    print("Milestone 35 Phase 5 Step 3 input discovery assertions passed.")


if __name__ == "__main__":
    main()
