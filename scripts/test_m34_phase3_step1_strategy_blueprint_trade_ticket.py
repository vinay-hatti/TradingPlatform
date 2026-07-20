from datetime import date
from types import SimpleNamespace

from trading_ai.research_workstation.trade_construction import (
    TradeConstructionEngine,
    trade_construction_payload,
)


def main() -> None:
    legs = (
        SimpleNamespace(
            expiration=date(2026, 8, 21),
            option_type="PUT",
            side="SHORT",
            strike=100.0,
            bid=2.90,
            ask=3.10,
            mark=3.00,
            open_interest=8500,
            volume=1800,
            delta=-0.48,
            gamma=0.04,
            theta=-0.08,
            vega=0.12,
        ),
        SimpleNamespace(
            expiration=date(2026, 8, 21),
            option_type="PUT",
            side="LONG",
            strike=95.0,
            bid=1.10,
            ask=1.30,
            mark=1.20,
            open_interest=6000,
            volume=1200,
            delta=-0.20,
            gamma=0.03,
            theta=-0.05,
            vega=0.08,
        ),
    )

    profile = TradeConstructionEngine().construct(
        symbol="AAA",
        strategy_name="BULL_PUT_SPREAD",
        direction="BULLISH",
        legs=legs,
        account_equity=100_000.0,
        maximum_profit_per_contract=400.0,
        maximum_loss_per_contract=320.0,
        probability_of_profit=0.72,
        breakeven_points=(98.20,),
        requested_contracts=10,
    )

    assert profile.allowed is True
    assert profile.ticket.executable is True
    assert profile.ticket.ticket_status == "READY"
    assert profile.ticket.contracts == 10
    assert profile.blueprint.defined_risk is True
    assert profile.blueprint.order_side == "CREDIT"
    assert profile.blueprint.net_limit_price > 0
    assert profile.capital.total_maximum_risk == 3200.0
    assert profile.capital.position_risk_pct == 0.032
    assert profile.construction_score == 100.0
    assert profile.construction_grade == "A"
    assert not profile.rejection_reasons

    payload = trade_construction_payload(profile)
    assert payload["blueprint"]["symbol"] == "AAA"
    assert payload["ticket"]["contracts"] == 10
    assert payload["metadata"]["phase"] == 3

    print(
        "All Milestone 34 Phase 3 Step 1 strategy-blueprint "
        "and trade-ticket assertions passed."
    )


if __name__ == "__main__":
    main()
