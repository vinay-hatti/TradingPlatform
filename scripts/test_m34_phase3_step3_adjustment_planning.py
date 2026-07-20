from datetime import date

from trading_ai.research_workstation.trade_lifecycle import (
    TradeLifecycleEngine,
)


def main() -> None:
    profile = TradeLifecycleEngine().plan(
        symbol="BBB",
        strategy_name="BEAR_CALL_SPREAD",
        expiration=date(2026, 8, 1),
        as_of_date=date(2026, 7, 19),
        entry_limit_price=1.25,
        net_credit_debit=125.0,
        maximum_profit=250.0,
        maximum_loss=375.0,
        probability_of_profit=0.66,
        confidence=0.74,
        spread_pct=0.10,
        defined_risk=True,
        current_delta_exposure=-0.42,
        event_date=date(2026, 7, 20),
    )

    assert profile.allowed is True
    assert profile.exit.monitoring_frequency == "INTRADAY"
    assert any(
        action.action == "DELTA_HEDGE" and action.allowed
        for action in profile.adjustments
    )
    assert any(
        "event risk" in warning.lower()
        for warning in profile.warnings
    )
    assert profile.risk_severity in {"LOW", "MODERATE"}
    assert profile.entry.entry_status == "READY_WITH_WARNINGS"

    print(
        "Milestone 34 Phase 3 Step 3 adjustment-planning "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
