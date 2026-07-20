from datetime import date
from types import SimpleNamespace

from trading_ai.research_workstation.trade_construction import (
    TradeConstructionEngine,
)


def main() -> None:
    naked_short_call = (
        SimpleNamespace(
            expiration=date(2026, 8, 21),
            option_type="CALL",
            side="SHORT",
            strike=110.0,
            bid=1.80,
            ask=2.40,
            mark=2.10,
            open_interest=20,
            volume=5,
            delta=0.30,
            gamma=0.03,
            theta=-0.06,
            vega=0.10,
        ),
    )

    profile = TradeConstructionEngine().construct(
        symbol="RISK",
        strategy_name="SHORT_CALL",
        direction="BEARISH",
        legs=naked_short_call,
        account_equity=25_000.0,
        maximum_profit_per_contract=210.0,
        maximum_loss_per_contract=None,
        probability_of_profit=0.42,
        requested_contracts=5,
    )

    assert profile.allowed is False
    assert profile.ticket.executable is False
    assert profile.ticket.ticket_status == "REJECTED"
    assert profile.ticket.contracts == 0
    assert profile.risk_severity in {"HIGH", "CRITICAL"}
    assert profile.rejection_reasons
    assert profile.warnings
    failed = {
        check.name
        for check in profile.checks
        if not check.passed
    }
    assert "DEFINED_RISK" in failed
    assert "POSITION_RISK" in failed
    assert "PROBABILITY_OF_PROFIT" in failed
    assert "BID_ASK_SPREAD" in failed
    assert "OPEN_INTEREST" in failed
    assert "OPTION_VOLUME" in failed

    print(
        "Milestone 34 Phase 3 Step 1 trade-construction "
        "governance assertions passed."
    )


if __name__ == "__main__":
    main()
