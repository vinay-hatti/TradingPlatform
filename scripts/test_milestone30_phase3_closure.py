from __future__ import annotations

import ast
from pathlib import Path


REQUIRED_MODULES = (
    "src/trading_ai/broker/broker_policy.py",
    "src/trading_ai/broker/broker_profile.py",
    "src/trading_ai/broker/broker_error.py",
    "src/trading_ai/broker/broker_adapter.py",
    "src/trading_ai/broker/broker_authentication_engine.py",
    "src/trading_ai/broker/broker_service.py",
    "src/trading_ai/broker/instrument_policy.py",
    "src/trading_ai/broker/instrument_profile.py",
    "src/trading_ai/broker/instrument_mapper.py",
    "src/trading_ai/broker/broker_order_policy.py",
    "src/trading_ai/broker/broker_order_profile.py",
    "src/trading_ai/broker/broker_order_validation_engine.py",
    "src/trading_ai/broker/broker_execution_policy.py",
    "src/trading_ai/broker/broker_execution_profile.py",
    "src/trading_ai/broker/broker_execution_adapter.py",
    "src/trading_ai/broker/broker_idempotency_registry.py",
    "src/trading_ai/broker/broker_execution_engine.py",
    "src/trading_ai/broker/broker_execution_service.py",
    "src/trading_ai/broker/broker_reconciliation_policy.py",
    "src/trading_ai/broker/broker_status_profile.py",
    "src/trading_ai/broker/broker_status_engine.py",
    "src/trading_ai/broker/broker_position_engine.py",
    "src/trading_ai/broker/broker_reconciliation_engine.py",
    "src/trading_ai/broker/broker_status_service.py",
    "src/trading_ai/broker/broker_operational_reporting.py",
)

REQUIRED_COMMANDS = (
    "broker-authentication-test",
    "broker-contract-mapping-test",
    "broker-order-execution-test",
    "broker-status-reconciliation-test",
    "broker-operational-report",
    "milestone30-phase3-regression-test",
    "milestone30-phase3-closure-test",
)


def main() -> None:
    missing = [path for path in REQUIRED_MODULES if not Path(path).exists()]
    assert not missing, "Missing Phase 3 modules: " + ", ".join(missing)

    cli_path = Path("src/trading_ai/__main__.py")
    assert cli_path.exists(), "Active CLI file is missing."
    source = cli_path.read_text(encoding="utf-8")
    ast.parse(source)

    for command in REQUIRED_COMMANDS:
        assert command in source, f"Missing CLI command: {command}"

    report_source = Path(
        "src/trading_ai/broker/broker_operational_reporting.py"
    ).read_text(encoding="utf-8")

    for heading in (
        "Broker Authentication and Readiness",
        "Order Submission, Cancellation, Replacement, and Idempotency",
        "Order Status, Fills, Commissions, and Fees",
        "Position Synchronization and Reconciliation",
        "Broker Operational Diagnostics",
    ):
        assert heading in report_source, f"Missing report section: {heading}"

    print("All Milestone 30 Phase 3 closure assertions passed.")


if __name__ == "__main__":
    main()
