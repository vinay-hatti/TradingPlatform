from __future__ import annotations

import ast
from pathlib import Path


REQUIRED_MODULES = (
    "src/trading_ai/risk_gateway/pretrade_risk_policy.py",
    "src/trading_ai/risk_gateway/pretrade_risk_profile.py",
    "src/trading_ai/risk_gateway/pretrade_risk_engine.py",
    "src/trading_ai/risk_gateway/pretrade_risk_service.py",
    "src/trading_ai/risk_gateway/order_risk_mapper.py",
    "src/trading_ai/risk_gateway/portfolio_risk_policy.py",
    "src/trading_ai/risk_gateway/portfolio_risk_profile.py",
    "src/trading_ai/risk_gateway/portfolio_exposure_engine.py",
    "src/trading_ai/risk_gateway/position_limit_engine.py",
    "src/trading_ai/risk_gateway/portfolio_risk_engine.py",
    "src/trading_ai/risk_gateway/options_risk_policy.py",
    "src/trading_ai/risk_gateway/options_risk_profile.py",
    "src/trading_ai/risk_gateway/options_greeks_engine.py",
    "src/trading_ai/risk_gateway/options_scenario_engine.py",
    "src/trading_ai/risk_gateway/strategy_margin_engine.py",
    "src/trading_ai/risk_gateway/options_risk_engine.py",
    "src/trading_ai/risk_gateway/trading_control_policy.py",
    "src/trading_ai/risk_gateway/trading_control_profile.py",
    "src/trading_ai/risk_gateway/trading_control_repository.py",
    "src/trading_ai/risk_gateway/trading_control_engine.py",
    "src/trading_ai/risk_gateway/risk_gateway_service.py",
    "src/trading_ai/risk_gateway/order_workflow_risk_guard.py",
    "src/trading_ai/risk_gateway/risk_gateway_decision_bridge.py",
    "src/trading_ai/risk_gateway/risk_gateway_reporting.py",
)

REQUIRED_COMMANDS = (
    "pretrade-risk-test",
    "portfolio-risk-controls-test",
    "options-risk-test",
    "trading-controls-risk-gateway-test",
    "risk-gateway-decision-integration-test",
    "risk-gateway-report",
    "milestone30-phase5-regression-test",
    "milestone30-phase5-closure-test",
)


def main() -> None:
    missing = [path for path in REQUIRED_MODULES if not Path(path).exists()]
    assert not missing, "Missing Phase 5 modules: " + ", ".join(missing)

    cli_path = Path("src/trading_ai/__main__.py")
    assert cli_path.exists(), "Active CLI file is missing."
    source = cli_path.read_text(encoding="utf-8")
    ast.parse(source)
    for command in REQUIRED_COMMANDS:
        assert command in source, f"Missing CLI command: {command}"

    report_source = Path(
        "src/trading_ai/risk_gateway/risk_gateway_reporting.py"
    ).read_text(encoding="utf-8")
    for heading in (
        "Combined Risk-Gateway Decisions",
        "Order-Level Notional, Premium, and Buying-Power Risk",
        "Portfolio Exposure, Concentration, and Position Limits",
        "Options Greeks, Scenario Stress, and Strategy Margin",
        "Daily Loss, Drawdown, Kill-Switch, and Trading Halts",
        "Risk-Gateway Operational Diagnostics",
    ):
        assert heading in report_source, f"Missing report section: {heading}"

    bridge_source = Path(
        "src/trading_ai/risk_gateway/risk_gateway_decision_bridge.py"
    ).read_text(encoding="utf-8")
    for field in (
        "risk_gateway_allowed",
        "risk_gateway_score",
        "risk_gateway_recommendation",
        "execution_permitted",
    ):
        assert field in bridge_source, f"Missing Decision Engine field: {field}"

    print("All Milestone 30 Phase 5 closure assertions passed.")


if __name__ == "__main__":
    main()
