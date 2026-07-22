import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.institutional_decision_cli import run


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        comparison_path = (
            root / "amzn_call_strategy_comparison.json"
        )
        output_dir = root / "institutional_decision"

        comparison_path.write_text(
            json.dumps(
                {
                    "symbol": "AMZN",
                    "direction": "CALL",
                    "warnings": [],
                    "ranked_strategies": [
                        {
                            "strategy_id": "AMZN:APPROVED",
                            "symbol": "AMZN",
                            "direction": "CALL",
                            "expiry": "2026-08-21",
                            "strategy_type": "BULL_CALL_SPREAD",
                            "institutional_score": 75.0,
                            "liquidity_score": 90.0,
                            "probability_proxy": 0.55,
                            "reward_risk_ratio": 2.0,
                            "max_loss": 2.0,
                            "max_profit": 4.0,
                            "breakeven": 222.0,
                            "debit": 2.0,
                            "credit": None,
                            "quote_quality": "COMPLETE",
                            "warnings": [],
                            "legs": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        code = run(
            [
                "--strategy-comparison-json",
                str(comparison_path),
                "--output-dir",
                str(output_dir),
            ]
        )
        assert code == 0

        output_path = (
            output_dir
            / "amzn_call_institutional_decision.json"
        )
        assert output_path.exists()
        payload = json.loads(
            output_path.read_text(encoding="utf-8")
        )
        assert payload["decision"] == "APPROVE"
        assert payload["paper_trade_ready"] is True

    print(
        "Milestone 35 Phase 5 Step 8 integration assertions passed."
    )


if __name__ == "__main__":
    main()
