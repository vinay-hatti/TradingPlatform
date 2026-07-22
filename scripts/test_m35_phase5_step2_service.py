import json
import tempfile
from datetime import date
from pathlib import Path

from trading_ai.scanner.intermarket_relationships.service import (
    IntermarketRelationshipService,
)


def main():
    records = [
        {"symbol": "SPY", "return_21d": 0.08, "governance_status": "READY"},
        {"symbol": "QQQ", "return_21d": 0.12, "governance_status": "READY"},
        {"symbol": "IWM", "return_21d": 0.10, "governance_status": "READY"},
        {"symbol": "^VIX", "return_21d": -0.15, "governance_status": "READY"},
        {"symbol": "IEF", "return_21d": -0.01, "governance_status": "READY"},
        {"symbol": "TLT", "return_21d": -0.03, "governance_status": "READY"},
        {"symbol": "LQD", "return_21d": 0.01, "governance_status": "READY"},
        {"symbol": "HYG", "return_21d": 0.04, "governance_status": "READY"},
        {"symbol": "UUP", "return_21d": -0.02, "governance_status": "READY"},
        {"symbol": "GLD", "return_21d": 0.01, "governance_status": "READY"},
        {"symbol": "USO", "return_21d": 0.02, "governance_status": "READY"},
    ]

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        input_path = root / "features.jsonl"
        output_path = root / "profile.json"

        with input_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")

        run_profile = IntermarketRelationshipService().run(
            as_of_date=date(2026, 7, 20),
            input_path=input_path,
            output_path=output_path,
        )

        assert output_path.exists()
        assert run_profile.records_read == 11
        assert run_profile.symbols_available == 11
        assert run_profile.symbols_missing == 0
        assert run_profile.market_state == "RISK_ON"
        assert run_profile.governance_status == "READY"

    print("Milestone 35 Phase 5 Step 2 service assertions passed.")


if __name__ == "__main__":
    main()
