from datetime import date

from trading_ai.research_workstation.trade_lifecycle import (
    TradeLifecycleEngine,
)


def main() -> None:
    profile = TradeLifecycleEngine().plan(
        symbol="RISK",
        strategy_name="NAKED_SHORT_CALL",
        expiration=date(2026, 7, 23),
        as_of_date=date(2026, 7, 19),
        entry_limit_price=2.00,
        net_credit_debit=200.0,
        maximum_profit=200.0,
        maximum_loss=None,
        probability_of_profit=0.40,
        confidence=0.45,
        spread_pct=0.35,
        defined_risk=False,
        current_delta_exposure=-0.65,
    )

    assert profile.allowed is False
    assert profile.entry.entry_status == "BLOCKED"
    assert profile.rejection_reasons
    assert profile.risk_severity in {"HIGH", "CRITICAL"}
    assert "Days to expiration below minimum policy." in (
        profile.rejection_reasons
    )
    assert "Entry confidence below policy threshold." in (
        profile.rejection_reasons
    )
    assert "Bid/ask spread exceeds entry policy." in (
        profile.rejection_reasons
    )
    assert "Defined-risk structure is required." in (
        profile.rejection_reasons
    )
    assert any(
        action.action == "DELTA_HEDGE" and action.allowed
        for action in profile.adjustments
    )

    print(
        "Milestone 34 Phase 3 Step 3 lifecycle-governance "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
