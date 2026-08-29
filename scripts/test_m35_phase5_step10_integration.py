import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.paper_trade_lifecycle_cli import run


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        input_path = root / "preparation.json"
        output_dir = root / "paper_trade"
        registry_path = root / "registry.json"

        input_path.write_text(
            json.dumps(
                {
                    "symbol": "AMZN",
                    "direction": "CALL",
                    "strategy_id": "AMZN:INTEGRATION",
                    "strategy_type": "BULL_CALL_SPREAD",
                    "paper_trade_ready": True,
                    "paper_trade_payload": {
                        "strategy_id": "AMZN:INTEGRATION",
                        "symbol": "AMZN",
                        "direction": "CALL",
                        "strategy_type": "BULL_CALL_SPREAD",
                        "expiry": "2026-08-21",
                        "limit_debit": 1.30,
                        "max_profit": 3.70,
                        "max_loss": 1.30,
                        "breakeven": 271.30,
                        "reward_risk_ratio": 2.846,
                        "legs": [
                            {
                                "symbol": "AMZN",
                                "expiry": "2026-08-21",
                                "strike": 270,
                                "option_type": "CALL",
                                "action": "BUY",
                                "quantity": 1,
                                "bid": 5.40,
                                "ask": 5.60,
                            },
                            {
                                "symbol": "AMZN",
                                "expiry": "2026-08-21",
                                "strike": 275,
                                "option_type": "CALL",
                                "action": "SELL",
                                "quantity": 1,
                                "bid": 4.30,
                                "ask": 4.50,
                            },
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )

        code = run(
            [
                "--paper-trade-preparation-json",
                str(input_path),
                "--output-dir",
                str(output_dir),
                "--registry-file",
                str(registry_path),
            ]
        )
        assert code == 0
        assert registry_path.exists()
        outputs = list(output_dir.glob("*_lifecycle.json"))
        assert len(outputs) == 1

        payload = json.loads(
            outputs[0].read_text(encoding="utf-8")
        )
        assert payload["order"]["status"] == "FILLED"
        assert payload["position"]["status"] == "OPEN"

    print(
        "Milestone 35 Phase 5 Step 10 integration assertions passed."
    )


if __name__ == "__main__":
    main()
