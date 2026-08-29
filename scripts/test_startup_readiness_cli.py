from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


def load_cli():
    path = Path("src/trading_ai/__main__.py")
    spec = importlib.util.spec_from_file_location("milestone30_cli", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def assert_command(module, command: str, script: str) -> None:
    with patch.object(module, "run_script") as runner:
        with patch.object(sys, "argv", ["trading_ai", command, "--sample", "1"]):
            module.main()
        runner.assert_called_once_with(script, ["--sample", "1"])


def main() -> None:
    module = load_cli()
    assert_command(
        module,
        "production-runtime-safety-test",
        "scripts/test_production_runtime_safety.py",
    )
    assert_command(
        module,
        "environment-registry-test",
        "scripts/test_environment_configuration_registry.py",
    )
    assert_command(
        module,
        "secret-governance-test",
        "scripts/test_secret_governance.py",
    )
    assert_command(
        module,
        "startup-readiness-check",
        "scripts/run_startup_readiness_check.py",
    )
    assert_command(
        module,
        "startup-readiness-test",
        "scripts/test_startup_readiness_gate.py",
    )
    print("All Milestone 30 Phase 1 startup-readiness CLI assertions passed.")


if __name__ == "__main__":
    main()
