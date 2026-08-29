from __future__ import annotations

import ast
from pathlib import Path


MODULES = [
    "adaptive_strategy_policy.py",
    "adaptive_strategy_profile.py",
    "adaptive_strategy_engine.py",
    "adaptive_strategy_service.py",
    "adaptive_strategy_serialization.py",
    "adaptive_strategy_integration.py",
    "strategy_learning_policy.py",
    "strategy_learning_profile.py",
    "strategy_learning_dataset.py",
    "strategy_learning_engine.py",
    "strategy_learning_service.py",
    "strategy_learning_serialization.py",
    "ensemble_decision_policy.py",
    "ensemble_decision_profile.py",
    "ensemble_decision_engine.py",
    "ensemble_decision_service.py",
    "ensemble_decision_serialization.py",
    "ensemble_decision_integration.py",
    "online_adaptation_policy.py",
    "online_adaptation_profile.py",
    "online_adaptation_engine.py",
    "online_adaptation_service.py",
    "online_adaptation_serialization.py",
    "learning_state_registry.py",
    "phase10_decision_integration_policy.py",
    "phase10_decision_integration_profile.py",
    "phase10_decision_integration_service.py",
    "phase10_decision_integration_serialization.py",
]

TESTS = [
    "test_adaptive_strategy_foundation.py",
    "test_strategy_learning.py",
    "test_ensemble_decision.py",
    "test_online_adaptation.py",
    "test_phase10_decision_integration.py",
    "test_phase10_decision_contract.py",
    "test_phase10_reporting.py",
    "test_phase10_cli.py",
    "test_phase10_regression.py",
    "test_phase10_closure.py",
]

COMMANDS = [
    "adaptive-strategy-test",
    "strategy-learning-test",
    "ensemble-decision-test",
    "online-adaptation-test",
    "phase10-decision-integration-test",
    "phase10-decision-contract-test",
    "phase10-report-test",
    "phase10-cli-test",
    "phase10-regression-test",
    "phase10-closure-test",
]


def active_or_replacement(active: str, replacement: str) -> Path:
    a = Path(active)
    return a if a.exists() else Path(replacement)


def main() -> None:
    strategy = Path("src/trading_ai/strategy_engine")
    missing_modules = [name for name in MODULES if not (strategy / name).exists()]
    assert not missing_modules, f"Missing Phase 10 modules: {missing_modules}"

    missing_tests = [name for name in TESTS if not (Path("scripts") / name).exists()]
    assert not missing_tests, f"Missing Phase 10 tests: {missing_tests}"

    cli = active_or_replacement("src/trading_ai/__main__.py", "src/trading_ai/phase10_step7___main__.py")
    assert cli.exists(), "Phase 10 CLI replacement is unavailable"
    cli_source = cli.read_text()
    ast.parse(cli_source)
    for command in COMMANDS:
        assert f'sub.add_parser("{command}")' in cli_source, command

    report = active_or_replacement(
        "src/trading_ai/backtest/report.py",
        "src/trading_ai/backtest/phase10_step6_report.py",
    )
    assert report.exists(), "Phase 10 report replacement is unavailable"
    report_source = report.read_text()
    ast.parse(report_source)
    for marker in [
        "Adaptive Strategy Selection",
        "Ensemble Decision Intelligence",
        "Online Adaptation",
        "Learning-State Registry",
    ]:
        assert marker in report_source, marker

    decision_files = {
        "institutional_decision.py": "phase10_step5_institutional_decision.py",
        "decision_run_result.py": "phase10_step5_decision_run_result.py",
        "institutional_decision_engine.py": "phase10_step5_institutional_decision_engine.py",
    }
    for active_name, replacement_name in decision_files.items():
        path = active_or_replacement(
            str(strategy / active_name),
            str(strategy / replacement_name),
        )
        assert path.exists(), f"Missing {active_name} replacement"
        ast.parse(path.read_text())

    print("All Phase 10 closure assertions passed.")


if __name__ == "__main__":
    main()
