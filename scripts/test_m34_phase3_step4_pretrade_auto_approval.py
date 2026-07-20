from types import SimpleNamespace

from trading_ai.research_workstation.pretrade_governance import (
    PreTradeGovernanceEngine,
    governance_decision_payload,
)


def build_inputs(
    *,
    position_risk_pct: float = 0.03,
    portfolio_risk_pct: float = 0.08,
    construction_score: float = 96.0,
    portfolio_health_score: float = 92.0,
    lifecycle_score: float = 95.0,
):
    leg = SimpleNamespace(
        spread_pct=0.08,
        open_interest=5000,
        volume=1000,
    )
    blueprint = SimpleNamespace(
        defined_risk=True,
        probability_of_profit=0.72,
        reward_risk_ratio=1.25,
        legs=(leg,),
    )
    capital = SimpleNamespace(
        position_risk_pct=position_risk_pct,
    )
    ticket = SimpleNamespace(executable=True)
    construction = SimpleNamespace(
        blueprint=blueprint,
        capital=capital,
        ticket=ticket,
        construction_score=construction_score,
        allowed=True,
    )
    exposure = SimpleNamespace(
        portfolio_delta=120.0,
        portfolio_gamma=-15.0,
        portfolio_vega=-80.0,
    )
    health = SimpleNamespace(
        portfolio_health_score=portfolio_health_score,
        portfolio_risk_pct=portfolio_risk_pct,
        capital_utilization_pct=0.35,
    )
    allocation = SimpleNamespace(
        exposure=exposure,
        health=health,
        allowed=True,
    )
    entry = SimpleNamespace(entry_allowed=True)
    lifecycle = SimpleNamespace(
        entry=entry,
        lifecycle_score=lifecycle_score,
        allowed=True,
    )
    return construction, allocation, lifecycle


def main() -> None:
    construction, allocation, lifecycle = build_inputs()
    profile = PreTradeGovernanceEngine().evaluate(
        trade_id="TRADE-001",
        symbol="AAA",
        strategy_name="BULL_PUT_SPREAD",
        trade_construction=construction,
        portfolio_allocation=allocation,
        lifecycle=lifecycle,
        broker_ready=True,
        compliance_cleared=True,
    )

    assert profile.allowed is True
    assert profile.approval_status == "AUTO_APPROVED"
    assert profile.governance_score == 100.0
    assert profile.governance_grade == "A"
    assert profile.risk_severity == "NONE"
    assert not profile.warnings
    assert not profile.rejection_reasons
    assert len(profile.rules) == 22
    assert len(profile.audit_trail) == 22
    assert profile.metadata["step"] == 4

    payload = governance_decision_payload(profile)
    assert payload["trade_id"] == "TRADE-001"
    assert payload["approval_status"] == "AUTO_APPROVED"

    print(
        "All Milestone 34 Phase 3 Step 4 auto-approval "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
