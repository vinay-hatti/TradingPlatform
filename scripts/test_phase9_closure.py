from __future__ import annotations

import ast
from pathlib import Path


REQUIRED_GOVERNANCE_MODULES = (
    "execution_governance_policy.py",
    "execution_governance_profile.py",
    "execution_governance_engine.py",
    "execution_governance_service.py",
    "execution_governance_serialization.py",
    "execution_route_governance_policy.py",
    "execution_route_registry_profile.py",
    "execution_route_registry_serialization.py",
    "execution_route_promotion_engine.py",
    "execution_route_registry.py",
    "execution_route_registry_service.py",
    "execution_champion_challenger_policy.py",
    "execution_champion_challenger_profile.py",
    "execution_champion_challenger_engine.py",
    "execution_champion_challenger_service.py",
    "execution_champion_challenger_serialization.py",
    "execution_governance_integration_policy.py",
    "execution_governance_integration_profile.py",
    "execution_governance_integration_service.py",
    "execution_governance_integration_serialization.py",
)

REQUIRED_TESTS = (
    "test_execution_analytics.py",
    "test_execution_aggregation.py",
    "test_execution_benchmark_routing.py",
    "test_execution_integration.py",
    "test_execution_reporting.py",
    "test_execution_governance.py",
    "test_execution_route_registry.py",
    "test_execution_champion_challenger.py",
    "test_execution_governance_integration.py",
    "test_execution_governance_decision_contract.py",
    "test_execution_governance_reporting.py",
    "test_execution_governance_cli.py",
    "test_phase9_regression.py",
)

REQUIRED_CLI_COMMANDS = (
    "execution-analytics-test",
    "execution-aggregation-test",
    "execution-benchmark-routing-test",
    "execution-integration-test",
    "execution-report-test",
    "execution-governance-test",
    "execution-route-registry-test",
    "execution-champion-challenger-test",
    "execution-governance-integration-test",
    "execution-governance-decision-contract-test",
    "execution-governance-report-test",
    "phase9-regression-test",
    "phase9-closure-test",
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    strategy = root / "src" / "trading_ai" / "strategy_engine"
    scripts = root / "scripts"
    cli = root / "src" / "trading_ai" / "__main__.py"

    missing_modules = [name for name in REQUIRED_GOVERNANCE_MODULES if not (strategy / name).exists()]
    missing_tests = [name for name in REQUIRED_TESTS if not (scripts / name).exists()]

    assert not missing_modules, f"Missing Phase 9 governance modules: {missing_modules}"
    assert not missing_tests, f"Missing Phase 9 regression scripts: {missing_tests}"
    assert cli.exists(), "Missing src/trading_ai/__main__.py"

    source = cli.read_text(encoding="utf-8")
    ast.parse(source)
    missing_commands = [command for command in REQUIRED_CLI_COMMANDS if command not in source]
    assert not missing_commands, f"Missing Phase 9 CLI commands: {missing_commands}"

    report = root / "src" / "trading_ai" / "backtest" / "report.py"
    assert report.exists(), "Missing reporting/report.py"
    report_source = report.read_text(encoding="utf-8")
    assert "Execution Governance" in report_source
    assert "Champion" in report_source and "Challenger" in report_source
    assert "Route Registry" in report_source

    print("All Phase 9 closure assertions passed.")


if __name__ == "__main__":
    main()
