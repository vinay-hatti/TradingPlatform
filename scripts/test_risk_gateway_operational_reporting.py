from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.risk_gateway.risk_gateway_reporting import (
    RiskGatewayOperationalReport,
)


def main() -> None:
    decisions = (
        {
            "allowed": True,
            "aggregate_id": "agg-001",
            "client_order_id": "client-001",
            "account_id": "PAPER-001",
            "score": 100.0,
            "grade": "A",
            "severity": "LOW",
            "recommendation": "APPROVE",
            "metadata": {
                "blocking_components": (),
                "decision_count": 4,
            },
            "order_level_decision": {
                "aggregate_id": "agg-001",
                "recommendation": "APPROVE",
                "exposure": {
                    "gross_notional": 500.0,
                    "gross_premium": 500.0,
                    "buying_power_required": 500.0,
                    "risk_classification":
                        "DEFINED_RISK_LONG_OPTION",
                },
            },
            "portfolio_decision": {
                "aggregate_id": "agg-001",
                "recommendation": "APPROVE",
                "exposure": {
                    "projected_gross_exposure": 500.0,
                    "projected_net_exposure": 500.0,
                    "projected_buying_power_utilization": 0.01,
                    "projected_open_positions": 1,
                    "new_positions": 1,
                },
            },
            "options_decision": {
                "aggregate_id": "agg-001",
                "recommendation": "APPROVE",
                "greeks": {
                    "delta": 50.0,
                    "gamma": 2.0,
                    "vega": 18.0,
                },
                "worst_scenario": {"loss": 300.0},
                "margin": {
                    "strategy_classification":
                        "DEFINED_RISK_LONG_OPTION",
                    "margin_required": 500.0,
                },
            },
            "trading_control_decision": {
                "aggregate_id": "agg-001",
                "recommendation": "APPROVE",
                "reduce_only": False,
                "session": {
                    "daily_realized_pnl": -100.0,
                    "daily_unrealized_pnl": 50.0,
                    "intraday_drawdown": 250.0,
                },
                "control_state": {
                    "kill_switch": {"active": False},
                },
            },
            "warnings": (),
            "rejection_reasons": (),
        },
    )

    report = RiskGatewayOperationalReport()
    assert "Combined Risk-Gateway Decisions" in report.summary_html(decisions)
    assert "Order-Level Notional, Premium, and Buying-Power Risk" in report.order_risk_html(decisions)
    assert "Portfolio Exposure, Concentration, and Position Limits" in report.portfolio_html(decisions)
    assert "Options Greeks, Scenario Stress, and Strategy Margin" in report.options_html(decisions)
    assert "Daily Loss, Drawdown, Kill-Switch, and Trading Halts" in report.controls_html(decisions)

    with tempfile.TemporaryDirectory() as temp:
        path = report.generate(
            decisions=decisions,
            path=Path(temp) / "risk_gateway.html",
        )
        html = path.read_text(encoding="utf-8")
        assert "Pre-Trade Risk Gateway Operations" in html
        assert "agg-001" in html
        assert "DEFINED_RISK_LONG_OPTION" in html
        assert "APPROVE" in html

    print("All risk-gateway operational reporting assertions passed.")


if __name__ == "__main__":
    main()
