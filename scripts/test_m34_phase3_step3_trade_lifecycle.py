from datetime import date

from trading_ai.research_workstation.trade_lifecycle import (
    TradeLifecycleEngine,
    trade_lifecycle_payload,
)


def main() -> None:
    profile = TradeLifecycleEngine().plan(
        symbol="AAA",
        strategy_name="BULL_PUT_SPREAD",
        expiration=date(2026, 8, 21),
        as_of_date=date(2026, 7, 19),
        entry_limit_price=1.80,
        net_credit_debit=180.0,
        maximum_profit=400.0,
        maximum_loss=320.0,
        probability_of_profit=0.72,
        confidence=0.82,
        spread_pct=0.08,
        defined_risk=True,
        current_delta_exposure=0.18,
    )

    assert profile.allowed is True
    assert profile.entry.entry_status == "READY"
    assert profile.entry.entry_window == "PREFERRED"
    assert profile.entry.days_to_expiration == 33
    assert profile.exit.profit_target_value == 200.0
    assert profile.exit.stop_loss_value == 240.0
    assert profile.exit.monitoring_frequency == "DAILY"
    assert profile.lifecycle_score == 100.0
    assert profile.lifecycle_grade == "A"
    assert len(profile.adjustments) == 4
    assert len(profile.checkpoints) == 5
    assert profile.metadata["step"] == 3

    payload = trade_lifecycle_payload(profile)
    assert payload["symbol"] == "AAA"
    assert payload["entry"]["entry_allowed"] is True
    assert payload["exit"]["time_exit_dte"] == 7

    print(
        "All Milestone 34 Phase 3 Step 3 trade-lifecycle "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
