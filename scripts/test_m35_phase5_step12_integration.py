import json
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.dashboard_workflow_cli import run


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "workflow.json"

        payloads = {
            "market": {"symbol": "AMZN", "direction": "CALL"},
            "candidate": {"symbol": "AMZN", "direction": "CALL"},
            "chain": {"symbol": "AMZN", "direction": "CALL"},
            "strategy": {
                "symbol": "AMZN",
                "direction": "CALL",
                "generated_strategies": 175,
                "ranked_strategies": 20,
            },
            "decision": {
                "symbol": "AMZN",
                "direction": "CALL",
                "decision": "APPROVE",
            },
            "preparation": {
                "symbol": "AMZN",
                "direction": "CALL",
                "decision": "READY",
                "paper_trade_ready": True,
            },
            "lifecycle": {
                "order": {"status": "FILLED"},
                "position": {"status": "OPEN"},
            },
            "performance": {
                "summary": {
                    "total_positions": 1,
                    "total_pnl": 10.0,
                }
            },
        }

        paths = {}
        for name, payload in payloads.items():
            path = root / f"{name}.json"
            path.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
            paths[name] = path

        code = run(
            [
                "--market-scan-json", str(paths["market"]),
                "--candidate-inspection-json", str(paths["candidate"]),
                "--option-chain-json", str(paths["chain"]),
                "--strategy-comparison-json", str(paths["strategy"]),
                "--institutional-decision-json", str(paths["decision"]),
                "--paper-trade-preparation-json", str(paths["preparation"]),
                "--paper-trade-lifecycle-json", str(paths["lifecycle"]),
                "--performance-json", str(paths["performance"]),
                "--output-file", str(output),
            ]
        )

        assert code == 0
        assert output.exists()

        payload = json.loads(
            output.read_text(encoding="utf-8")
        )
        assert payload["workflow_status"] == "COMPLETE"
        assert payload["completed_stages"] == 8

    print(
        "Milestone 35 Phase 5 Step 12 integration assertions passed."
    )


if __name__ == "__main__":
    main()
