from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


def load_cli():
    path = Path("src/trading_ai/__main__.py")
    spec = importlib.util.spec_from_file_location("m30_phase4_cli", path)
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
        "canonical-order-lifecycle-test":
            "scripts/test_canonical_order_aggregate_lifecycle.py",
        "order-repository-test":
            "scripts/test_order_repository_journal_audit.py",
        "order-routing-workflow-test":
            "scripts/test_order_routing_workflow.py",
        "order-linkage-recovery-test":
            "scripts/test_parent_child_bracket_oco_recovery.py",
        "order-management-report":
            "scripts/build_order_management_report.py",
        "milestone30-phase4-regression-test":
            "scripts/test_milestone30_phase4_regression.py",
        "milestone30-phase4-closure-test":
            "scripts/test_milestone30_phase4_closure.py",
    }

    for command, script in mappings.items():
        assert_command(module, command, script)

    print("All Milestone 30 Phase 4 CLI assertions passed.")


if __name__ == "__main__":
    main()
