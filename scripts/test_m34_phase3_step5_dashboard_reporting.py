from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from trading_ai.research_workstation.phase3_dashboard import (
    Phase3DashboardEngine,
    phase3_dashboard_payload,
    render_phase3_dashboard_html,
    write_phase3_dashboard_html,
    write_phase3_dashboard_json,
)


def build_profiles():
    construction = SimpleNamespace(
        construction_score=96.0,
        construction_grade="A",
        allowed=True,
        warnings=(),
        rejection_reasons=(),
        blueprint=SimpleNamespace(
            defined_risk=True,
            reward_risk_ratio=1.25,
        ),
        capital=SimpleNamespace(position_risk_pct=0.03),
        ticket=SimpleNamespace(
            ticket_status="READY",
            executable=True,
        ),
    )

    allocation = SimpleNamespace(
        allowed=True,
        positions_allocated=2,
        warnings=(),
        rejection_reasons=(),
        health=SimpleNamespace(
            portfolio_health_score=91.0,
            portfolio_health_grade="A",
            portfolio_risk_pct=0.08,
            capital_utilization_pct=0.35,
            risk_severity="NONE",
        ),
        exposure=SimpleNamespace(portfolio_delta=125.0),
    )

    lifecycle = SimpleNamespace(
        lifecycle_score=95.0,
        lifecycle_grade="A",
        allowed=True,
        warnings=(),
        rejection_reasons=(),
        entry=SimpleNamespace(
            entry_status="READY",
            entry_allowed=True,
            days_to_expiration=33,
        ),
        exit=SimpleNamespace(
            profit_target_value=200.0,
            stop_loss_value=240.0,
        ),
    )

    governance = SimpleNamespace(
        governance_score=100.0,
        governance_grade="A",
        confidence_score=94.0,
        risk_severity="NONE",
        approval_status="AUTO_APPROVED",
        approval_recommendation="Trade may proceed automatically.",
        allowed=True,
        warnings=(),
        rejection_reasons=(),
        remediation_actions=(),
        rules=tuple(range(22)),
        audit_trail=tuple(range(22)),
    )

    return construction, allocation, lifecycle, governance


def main() -> None:
    construction, allocation, lifecycle, governance = build_profiles()

    profile = Phase3DashboardEngine().build(
        trade_id="TRADE-001",
        symbol="AAA",
        strategy_name="BULL_PUT_SPREAD",
        trade_construction=construction,
        portfolio_allocation=allocation,
        lifecycle=lifecycle,
        governance=governance,
    )

    assert profile.execution_allowed is True
    assert profile.overall_status == "READY"
    assert profile.overall_grade == "A"
    assert len(profile.sections) == 4
    assert profile.approval_status == "AUTO_APPROVED"
    assert profile.metadata["phase_status"] == "COMPLETE"

    payload = phase3_dashboard_payload(profile)
    assert payload["trade_id"] == "TRADE-001"
    assert payload["sections"][0]["section_id"] == "TRADE_CONSTRUCTION"

    html = render_phase3_dashboard_html(profile)
    assert "Milestone 34 Phase 3" in html
    assert "Trade Construction" in html
    assert "Position Sizing and Portfolio Allocation" in html
    assert "Trade Lifecycle" in html
    assert "Pre-Trade Governance" in html
    assert "AUTO_APPROVED" in html

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        json_path = write_phase3_dashboard_json(
            profile, tmp_path / "dashboard.json"
        )
        html_path = write_phase3_dashboard_html(
            profile, tmp_path / "dashboard.html"
        )
        assert json_path.exists()
        assert html_path.exists()
        assert "AUTO_APPROVED" in html_path.read_text(
            encoding="utf-8"
        )

    print(
        "All Milestone 34 Phase 3 Step 5 dashboard-reporting "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
