from types import SimpleNamespace

from trading_ai.research_workstation.pretrade_governance import (
    PreTradeGovernanceEngine,
)


def main() -> None:
    leg = SimpleNamespace(
        spread_pct=0.40,
        open_interest=10,
        volume=2,
    )
    construction = SimpleNamespace(
        blueprint=SimpleNamespace(
            defined_risk=False,
            probability_of_profit=0.35,
            reward_risk_ratio=0.25,
            legs=(leg,),
        ),
        capital=SimpleNamespace(position_risk_pct=0.20),
        ticket=SimpleNamespace(executable=False),
        construction_score=40.0,
        allowed=False,
    )
    allocation = SimpleNamespace(
        exposure=SimpleNamespace(
            portfolio_delta=9000.0,
            portfolio_gamma=2500.0,
            portfolio_vega=12000.0,
        ),
        health=SimpleNamespace(
            portfolio_health_score=25.0,
            portfolio_risk_pct=0.30,
            capital_utilization_pct=0.90,
        ),
        allowed=False,
    )
    lifecycle = SimpleNamespace(
        entry=SimpleNamespace(entry_allowed=False),
        lifecycle_score=30.0,
        allowed=False,
    )

    profile = PreTradeGovernanceEngine().evaluate(
        trade_id="TRADE-RISK",
        symbol="RISK",
        strategy_name="NAKED_SHORT_CALL",
        trade_construction=construction,
        portfolio_allocation=allocation,
        lifecycle=lifecycle,
        broker_ready=False,
        compliance_cleared=False,
        event_risk_present=True,
    )

    assert profile.allowed is False
    assert profile.approval_status == "REJECTED"
    assert profile.governance_grade == "F"
    assert profile.risk_severity == "CRITICAL"
    assert profile.rejection_reasons
    assert profile.warnings
    assert profile.remediation_actions
    assert "Compliance Clearance" in profile.residual_risks
    assert any(
        rule.rule_id == "CP-001"
        and not rule.passed
        and rule.blocking
        for rule in profile.rules
    )

    print(
        "All Milestone 34 Phase 3 Step 4 rejection-path "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
