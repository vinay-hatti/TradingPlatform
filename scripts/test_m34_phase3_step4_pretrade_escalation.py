from trading_ai.research_workstation.pretrade_governance import (
    PreTradeGovernanceEngine,
)

from test_m34_phase3_step4_pretrade_auto_approval import build_inputs


def main() -> None:
    construction, allocation, lifecycle = build_inputs(
        position_risk_pct=0.045,
        portfolio_risk_pct=0.08,
    )
    manager = PreTradeGovernanceEngine().evaluate(
        trade_id="TRADE-MGR",
        symbol="AAA",
        strategy_name="BULL_PUT_SPREAD",
        trade_construction=construction,
        portfolio_allocation=allocation,
        lifecycle=lifecycle,
        broker_ready=True,
        compliance_cleared=True,
    )
    assert manager.allowed is False
    assert manager.approval_status == "MANAGER_APPROVAL"
    assert any(
        item.level == "MANAGER"
        and item.required
        and item.status == "PENDING"
        for item in manager.approval_chain
    )

    construction, allocation, lifecycle = build_inputs(
        position_risk_pct=0.03,
        portfolio_risk_pct=0.12,
    )
    committee = PreTradeGovernanceEngine().evaluate(
        trade_id="TRADE-RC",
        symbol="BBB",
        strategy_name="IRON_CONDOR",
        trade_construction=construction,
        portfolio_allocation=allocation,
        lifecycle=lifecycle,
        broker_ready=True,
        compliance_cleared=True,
    )
    assert committee.allowed is False
    assert committee.approval_status == "RISK_COMMITTEE_APPROVAL"
    assert any(
        item.level == "RISK_COMMITTEE"
        and item.required
        and item.status == "PENDING"
        for item in committee.approval_chain
    )

    print(
        "All Milestone 34 Phase 3 Step 4 approval-escalation "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
