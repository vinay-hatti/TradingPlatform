from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


def load_cli():
    path = Path("src/trading_ai/__main__.py")
    spec = importlib.util.spec_from_file_location("m30_phase3_cli", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def assert_command(module, command: str, script: str) -> None:
    with patch.object(module, "run_script") as runner:
        with patch.object(
            sys,
            "argv",
            ["trading_ai", command, "--sample", "1"],
        ):
            module.main()
        runner.assert_called_once_with(script, ["--sample", "1"])


def main() -> None:
    module = load_cli()
    mappings = {
        "broker-authentication-test":
            "scripts/test_broker_authentication_foundation.py",
        "broker-contract-mapping-test":
            "scripts/test_broker_contract_mapping_orders.py",
        "broker-order-execution-test":
            "scripts/test_broker_order_execution_idempotency.py",
        "broker-status-reconciliation-test":
            "scripts/test_broker_status_fill_position_reconciliation.py",
        "broker-operational-report":
            "scripts/build_broker_operational_report.py",
        "milestone30-phase3-regression-test":
            "scripts/test_milestone30_phase3_regression.py",
        "milestone30-phase3-closure-test":
            "scripts/test_milestone30_phase3_closure.py",
    }

    for command, script in mappings.items():
        assert_command(module, command, script)

    print("All Milestone 30 Phase 3 CLI assertions passed.")


if __name__ == "__main__":
    main()
