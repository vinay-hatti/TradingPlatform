from __future__ import annotations

import ast
from pathlib import Path


REQUIRED_MODULES = (
    "src/trading_ai/order_management/order_policy.py",
    "src/trading_ai/order_management/order_profile.py",
    "src/trading_ai/order_management/order_event_contracts.py",
    "src/trading_ai/order_management/order_aggregate_engine.py",
    "src/trading_ai/order_management/order_state_machine.py",
    "src/trading_ai/order_management/order_service.py",
    "src/trading_ai/order_management/order_serialization.py",
    "src/trading_ai/order_management/order_repository_policy.py",
    "src/trading_ai/order_management/order_repository_profile.py",
    "src/trading_ai/order_management/order_repository.py",
    "src/trading_ai/order_management/order_event_journal.py",
    "src/trading_ai/order_management/order_audit_ledger.py",
    "src/trading_ai/order_management/order_persistence_service.py",
    "src/trading_ai/order_management/order_routing_policy.py",
    "src/trading_ai/order_management/order_routing_profile.py",
    "src/trading_ai/order_management/order_execution_router.py",
    "src/trading_ai/order_management/order_command_handler.py",
    "src/trading_ai/order_management/order_broker_mapper.py",
    "src/trading_ai/order_management/order_workflow_service.py",
    "src/trading_ai/order_management/order_linkage_policy.py",
    "src/trading_ai/order_management/order_linkage_profile.py",
    "src/trading_ai/order_management/order_group_engine.py",
    "src/trading_ai/order_management/order_group_repository.py",
    "src/trading_ai/order_management/order_group_workflow_service.py",
    "src/trading_ai/order_management/order_recovery_service.py",
    "src/trading_ai/order_management/order_management_reporting.py",
)

REQUIRED_COMMANDS = (
    "canonical-order-lifecycle-test",
    "order-repository-test",
    "order-routing-workflow-test",
    "order-linkage-recovery-test",
    "order-management-report",
    "milestone30-phase4-regression-test",
    "milestone30-phase4-closure-test",
)


def main() -> None:
    missing = [path for path in REQUIRED_MODULES if not Path(path).exists()]
    assert not missing, "Missing Phase 4 modules: " + ", ".join(missing)

    cli_path = Path("src/trading_ai/__main__.py")
    assert cli_path.exists(), "Active CLI file is missing."
    source = cli_path.read_text(encoding="utf-8")
    ast.parse(source)

    for command in REQUIRED_COMMANDS:
        assert command in source, f"Missing CLI command: {command}"

    report_source = Path(
        "src/trading_ai/order_management/order_management_reporting.py"
    ).read_text(encoding="utf-8")

    for heading in (
        "Canonical Order Aggregates and Lifecycle",
        "Command Handling, Broker Routing, and Workflow Orchestration",
        "Repository, Event Journal, Audit Ledger, and Concurrency",
        "Parent/Child, Bracket, and OCO Order Groups",
        "Cancel, Replace, and Recovery Governance",
        "Order Management Operational Diagnostics",
    ):
        assert heading in report_source, f"Missing report section: {heading}"

    print("All Milestone 30 Phase 4 closure assertions passed.")


if __name__ == "__main__":
    main()
