import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.paper_trade_preparation_cli import run


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        decision_path = root / "decision.json"
        quotes_path = root / "quotes.csv"
        output_dir = root / "output"

        decision_path.write_text(
            json.dumps(
                {
                    "symbol": "AMZN",
                    "direction": "CALL",
                    "decision": "APPROVE",
                    "selected_strategy": {
                        "strategy_id": "AMZN:TEST",
                        "symbol": "AMZN",
                        "direction": "CALL",
                        "strategy_type": "BULL_CALL_SPREAD",
                        "expiry": "2026-08-21",
                        "debit": 1.16,
                        "legs": [
                            {
                                "expiry": "2026-08-21",
                                "strike": 270,
                                "option_type": "CALL",
                                "action": "BUY",
                                "quantity": 1,
                            },
                            {
                                "expiry": "2026-08-21",
                                "strike": 275,
                                "option_type": "CALL",
                                "action": "SELL",
                                "quantity": 1,
                            },
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        with quotes_path.open(
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
                ],
            )
            writer.writeheader()
            writer.writerows(
                [
                    {
                        "underlying_symbol": "AMZN",
                        "expiry": "2026-08-21",
                        "strike": 270,
                        "option_type": "CALL",
                        "bid": 5.40,
                        "ask": 5.60,
                    },
                    {
                        "underlying_symbol": "AMZN",
                        "expiry": "2026-08-21",
                        "strike": 275,
                        "option_type": "CALL",
                        "bid": 4.30,
                        "ask": 4.50,
                    },
                ]
            )

        code = run(
            [
                "--institutional-decision-json",
                str(decision_path),
                "--quote-file",
                str(quotes_path),
                "--output-dir",
                str(output_dir),
            ]
        )
        assert code == 0

        output_path = (
            output_dir
            / "amzn_call_paper_trade_preparation.json"
        )
        assert output_path.exists()

        payload = json.loads(
            output_path.read_text(encoding="utf-8")
        )
        assert payload["paper_trade_ready"] is True
        assert payload["decision"] == "READY"

    print(
        "Milestone 35 Phase 5 Step 9 integration assertions passed."
    )


if __name__ == "__main__":
    main()
