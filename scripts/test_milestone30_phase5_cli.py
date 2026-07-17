from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


def load_cli():
    path = Path("src/trading_ai/__main__.py")
    spec = importlib.util.spec_from_file_location("m30_phase5_cli", path)
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
        "pretrade-risk-test":
            "scripts/test_pretrade_risk_foundation.py",
        "portfolio-risk-controls-test":
            "scripts/test_portfolio_exposure_controls.py",
        "options-risk-test":
            "scripts/test_options_greeks_scenario_margin.py",
        "trading-controls-risk-gateway-test":
            "scripts/test_trading_controls_risk_gateway_workflow.py",
        "risk-gateway-decision-integration-test":
            "scripts/test_risk_gateway_decision_integration.py",
        "risk-gateway-report":
            "scripts/build_risk_gateway_report.py",
        "milestone30-phase5-regression-test":
            "scripts/test_milestone30_phase5_regression.py",
        "milestone30-phase5-closure-test":
            "scripts/test_milestone30_phase5_closure.py",
    }
    for command, script in mappings.items():
        assert_command(module, command, script)

    print("All Milestone 30 Phase 5 CLI assertions passed.")


if __name__ == "__main__":
    main()
