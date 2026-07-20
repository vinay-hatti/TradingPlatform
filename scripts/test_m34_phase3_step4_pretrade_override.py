from trading_ai.research_workstation.pretrade_governance import (
    PreTradeGovernanceEngine,
)

from test_m34_phase3_step4_pretrade_auto_approval import build_inputs


def main() -> None:
    construction, allocation, lifecycle = build_inputs()
    lifecycle.allowed = False
    lifecycle.entry.entry_allowed = False

    profile = PreTradeGovernanceEngine().evaluate(
        trade_id="TRADE-OVERRIDE",
        symbol="AAA",
        strategy_name="BULL_PUT_SPREAD",
        trade_construction=construction,
        portfolio_allocation=allocation,
        lifecycle=lifecycle,
        broker_ready=True,
        compliance_cleared=True,
        override_requested=True,
        override_approved=True,
        override_reviewer="Risk Manager",
        override_reason="Documented event-risk exception.",
        override_scope=("LC-001",),
    )

    assert profile.override.requested is True
    assert profile.override.approved is True
    assert profile.override.reviewer == "Risk Manager"
    assert "Lifecycle Ready" in profile.residual_risks
    assert not profile.rejection_reasons
    assert profile.approval_status in {
        "AUTO_APPROVED",
        "APPROVED_WITH_WARNINGS",
        "REQUIRES_REVIEW",
    }
    assert any(
        record.rule_id == "LC-001"
        and record.reviewer == "Risk Manager"
        and record.notes == "Documented event-risk exception."
        for record in profile.audit_trail
    )

    print(
        "All Milestone 34 Phase 3 Step 4 override-audit "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
