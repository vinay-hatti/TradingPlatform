import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.paper_trade_performance_cli import run


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        lifecycle_dir = root / "paper_trade"
        lifecycle_dir.mkdir()
        mark_file = root / "marks.csv"
        output_file = root / "performance.json"

        lifecycle_path = (
            lifecycle_dir
            / "amzn_paper-test_lifecycle.json"
        )
        lifecycle_path.write_text(
            json.dumps(
                {
                    "order": {
                        "order_id": "PAPER-TEST",
                    },
                    "position": {
                        "position_id": "POSITION-TEST",
                        "strategy_id": "AMZN:INTEGRATION",
                        "symbol": "AMZN",
                        "status": "OPEN",
                        "quantity": 1,
                        "entry_debit": 1.30,
                    },
                    "events": [],
                }
            ),
            encoding="utf-8",
        )

        with mark_file.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "position_id",
                    "status",
                    "current_debit",
                    "marked_at",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "position_id": "POSITION-TEST",
                    "status": "OPEN",
                    "current_debit": 1.50,
                    "marked_at": (
                        "2026-07-21T16:00:00+00:00"
                    ),
                }
            )

        code = run(
            [
                "--lifecycle-dir",
                str(lifecycle_dir),
                "--mark-file",
                str(mark_file),
                "--output-file",
                str(output_file),
            ]
        )
        assert code == 0
        assert output_file.exists()

        payload = json.loads(
            output_file.read_text(encoding="utf-8")
        )
        assert payload["summary"]["total_positions"] == 1
        assert payload["summary"]["total_unrealized_pnl"] == 20.0

    print(
        "Milestone 35 Phase 5 Step 11 integration assertions passed."
    )


if __name__ == "__main__":
    main()
