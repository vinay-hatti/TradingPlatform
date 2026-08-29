import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.ranking_loader import (
    discover_symbol_data_files,
    load_ranking_records,
)


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory) / "reports"
        root.mkdir()

        empty = root / "ranking_snapshot.json"
        empty.write_text("[]", encoding="utf-8")

        populated = root / "scanner_results.json"
        populated.write_text(
            json.dumps(
                {
                    "run": {
                        "results": [
                            {
                                "ticker": "AAPL",
                                "score": 0.91,
                                "probability": 0.76,
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        found = discover_symbol_data_files((root,))
        assert len(found) == 1
        assert found[0].path == populated
        assert found[0].record_count == 1

        resolved, records = load_ranking_records(populated)
        assert resolved == populated
        assert records[0].symbol == "AAPL"

    print(
        "Milestone 35 Phase 5 Step 3 data discovery assertions passed."
    )


if __name__ == "__main__":
    main()
