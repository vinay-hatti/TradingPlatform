from types import SimpleNamespace

from trading_ai.research_workstation.phase3_dashboard import (
    Phase3DashboardEngine,
)


def main() -> None:
    construction = SimpleNamespace(
        construction_score=40.0,
        construction_grade="F",
        allowed=False,
        warnings=("Probability of profit is below policy.",),
        rejection_reasons=("Defined-risk structure is required.",),
        blueprint=SimpleNamespace(
            defined_risk=False,
            reward_risk_ratio=0.25,
        ),
        capital=SimpleNamespace(position_risk_pct=0.20),
        ticket=SimpleNamespace(
            ticket_status="REJECTED",
            executable=False,
        ),
    )
    allocation = SimpleNamespace(
        allowed=False,
        positions_allocated=0,
        warnings=("Portfolio diversification is below policy target.",),
        rejection_reasons=("No portfolio positions were allocated.",),
        health=SimpleNamespace(
            portfolio_health_score=20.0,
            portfolio_health_grade="F",
            portfolio_risk_pct=0.30,
            capital_utilization_pct=0.90,
            risk_severity="CRITICAL",
        ),
        exposure=SimpleNamespace(portfolio_delta=9000.0),
    )
    lifecycle = SimpleNamespace(
        lifecycle_score=30.0,
        lifecycle_grade="F",
        allowed=False,
        warnings=("Entry timing is outside preferred DTE.",),
        rejection_reasons=("Entry confidence below policy threshold.",),
        entry=SimpleNamespace(
            entry_status="BLOCKED",
            entry_allowed=False,
            days_to_expiration=4,
        ),
        exit=SimpleNamespace(
            profit_target_value=100.0,
            stop_loss_value=0.0,
        ),
    )
    governance = SimpleNamespace(
        governance_score=10.0,
        governance_grade="F",
        confidence_score=30.0,
        risk_severity="CRITICAL",
        approval_status="REJECTED",
        approval_recommendation="Do not submit the trade.",
        allowed=False,
        warnings=("Material event risk is present.",),
        rejection_reasons=("Compliance clearance is required.",),
        remediation_actions=(
            "Convert to a bounded-risk spread.",
            "Resolve compliance restrictions.",
        ),
        rules=tuple(range(22)),
        audit_trail=tuple(range(22)),
    )

    profile = Phase3DashboardEngine().build(
        trade_id="TRADE-RISK",
        symbol="RISK",
        strategy_name="NAKED_SHORT_CALL",
        trade_construction=construction,
        portfolio_allocation=allocation,
        lifecycle=lifecycle,
        governance=governance,
    )

    assert profile.execution_allowed is False
    assert profile.overall_status == "BLOCKED"
    assert profile.approval_status == "REJECTED"
    assert profile.risk_severity == "CRITICAL"
    assert profile.rejection_reasons
    assert profile.warnings
    assert profile.remediation_actions
    assert all(
        section.status == "BLOCKED"
        for section in profile.sections
    )

    print(
        "Milestone 34 Phase 3 Step 5 blocked-dashboard "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
