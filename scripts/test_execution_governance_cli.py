"""Phase 9 Step 5.6 command-routing regression test."""
from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import patch


EXPECTED = {
    "execution-governance-test": "scripts/test_execution_governance.py",
    "execution-route-registry-test": "scripts/test_execution_route_registry.py",
    "execution-champion-challenger-test": "scripts/test_execution_champion_challenger.py",
    "execution-governance-integration-test": "scripts/test_execution_governance_integration.py",
    "execution-governance-decision-contract-test": "scripts/test_execution_governance_decision_contract.py",
    "execution-governance-report-test": "scripts/test_execution_governance_reporting.py",
}


def verify_command(module, command: str, expected_script: str) -> None:
    captured: list[list[str]] = []

    def fake_run(cmd):
        captured.append(list(cmd))
        return SimpleNamespace(returncode=0)

    with patch.object(sys, "argv", ["trading_ai", command, "--sample", "42"]), patch.object(
        module.subprocess, "run", side_effect=fake_run
    ):
        try:
            module.main()
        except SystemExit as exc:
            assert exc.code == 0, (command, exc.code)

    assert len(captured) == 1, (command, captured)
    invoked = captured[0]
    assert invoked[0] == sys.executable
    assert invoked[1] == expected_script, (command, invoked)
    assert invoked[2:] == ["--sample", "42"], (command, invoked)


def main() -> None:
    module = importlib.import_module("trading_ai.__main__")
    for command, script in EXPECTED.items():
        verify_command(module, command, script)
    print("All execution-governance CLI assertions passed.")


if __name__ == "__main__":
    main()
