import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.filter_cli import _load_filter_records


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)

        list_path = root / "list.json"
        list_path.write_text(
            json.dumps(
                [
                    {
                        "symbol": "AMZN",
                        "institutional_score": 91,
                        "direction": "CALL",
                    },
                    {
                        "symbol": "LLY",
                        "institutional_score": 84,
                        "direction": "PUT",
                    },
                ]
            ),
            encoding="utf-8",
        )
        _, list_records = _load_filter_records(list_path)
        assert len(list_records) == 2
        assert list_records[0]["institutional_score"] == 91

        wrapped_path = root / "wrapped.json"
        wrapped_path.write_text(
            json.dumps(
                {
                    "live_trade_candidates": [
                        {
                            "symbol": "AVGO",
                            "institutional_score": 88,
                            "direction": "CALL",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        _, wrapped_records = _load_filter_records(wrapped_path)
        assert len(wrapped_records) == 1
        assert wrapped_records[0]["symbol"] == "AVGO"

    print(
        "Milestone 35 Phase 5 Step 4 raw-record loader assertions passed."
    )


if __name__ == "__main__":
    main()
