import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.filter_cli import run


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        rankings_path = root / "rankings.json"
        views_path = root / "saved_views.json"
        output_path = root / "filtered.json"

        rankings_path.write_text(
            json.dumps(
                [
                    {
                        "symbol": "AMZN",
                        "institutional_score": 91,
                        "probability_of_profit": 0.72,
                        "direction": "CALL",
                    },
                    {
                        "symbol": "LLY",
                        "institutional_score": 84,
                        "probability_of_profit": 0.64,
                        "direction": "PUT",
                    },
                ]
            ),
            encoding="utf-8",
        )

        assert (
            run(
                [
                    "--saved-views-json",
                    str(views_path),
                    "save",
                    "--name",
                    "Top Calls",
                    "--min-institutional-score",
                    "85",
                    "--directions",
                    "CALL",
                ]
            )
            == 0
        )

        assert (
            run(
                [
                    "--saved-views-json",
                    str(views_path),
                    "apply",
                    "--rankings-json",
                    str(rankings_path),
                    "--saved-view",
                    "Top Calls",
                    "--output-json",
                    str(output_path),
                ]
            )
            == 0
        )

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["input_records"] == 2
        assert payload["filtered_records"] == 1
        assert payload["records"][0]["symbol"] == "AMZN"

    print(
        "Milestone 35 Phase 5 Step 4 integration assertions passed."
    )


if __name__ == "__main__":
    main()
