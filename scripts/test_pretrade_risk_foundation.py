from __future__ import annotations

from trading_ai.order_management.order_profile import (
    CanonicalOrderAggregate,
    CanonicalOrderLeg,
)

from trading_ai.risk_gateway.order_risk_mapper import (
    canonical_order_to_risk_request,
)
from trading_ai.risk_gateway.pretrade_risk_policy import (
    PreTradeRiskPolicy,
)
from trading_ai.risk_gateway.pretrade_risk_profile import (
    PreTradeAccountProfile,
    PreTradeRiskLeg,
    PreTradeRiskRequest,
)
from trading_ai.risk_gateway.pretrade_risk_serialization import dumps
from trading_ai.risk_gateway.pretrade_risk_service import (
    PreTradeRiskService,
)


def main() -> None:
    account = PreTradeAccountProfile(
        account_id="PAPER-001",
        currency="USD",
        net_liquidation=100000.0,
        buying_power=200000.0,
        option_buying_power=100000.0,
        cash_balance=50000.0,
    )

    service = PreTradeRiskService()

    long_call = PreTradeRiskRequest(
        aggregate_id="agg-risk-001",
        client_order_id="client-risk-001",
        account_id="PAPER-001",
        order_type="LIMIT",
        time_in_force="DAY",
        strategy_name="LONG_CALL",
        legs=(
            PreTradeRiskLeg(
                leg_id="leg-1",
                symbol="AAPL_CALL",
                asset_class="OPTION",
                side="BUY_TO_OPEN",
                quantity=2,
                price=5.0,
                multiplier=100,
                strike=200.0,
                option_type="CALL",
                expiration="2026-08-21",
                metadata={"underlying_symbol": "AAPL"},
            ),
        ),
    )
    approved = service.evaluate(long_call, account)
    assert approved.allowed
    assert approved.recommendation == "APPROVE"
    assert approved.exposure is not None
    assert approved.exposure.gross_premium == 1000.0
    assert approved.exposure.buying_power_required == 1000.0
    assert approved.exposure.defined_risk
    assert (
        approved.exposure.risk_classification
        == "DEFINED_RISK_LONG_OPTION"
    )

    too_large = PreTradeRiskRequest(
        aggregate_id="agg-risk-002",
        client_order_id="client-risk-002",
        account_id="PAPER-001",
        order_type="LIMIT",
        time_in_force="DAY",
        legs=(
            PreTradeRiskLeg(
                leg_id="leg-1",
                symbol="AAPL",
                asset_class="EQUITY",
                side="BUY",
                quantity=1000,
                price=250.0,
            ),
        ),
    )
    rejected = service.evaluate(too_large, account)
    assert not rejected.allowed
    assert "MAXIMUM_ORDER_NOTIONAL" in rejected.rejection_reasons
    assert (
        "BUYING_POWER_CONCENTRATION"
        in rejected.rejection_reasons
    )
    assert (
        "NET_LIQUIDATION_CONCENTRATION"
        in rejected.rejection_reasons
    )

    undefined_policy = PreTradeRiskPolicy(
        reject_undefined_risk_option_orders=True,
    )
    undefined_service = PreTradeRiskService(undefined_policy)
    naked_short = PreTradeRiskRequest(
        aggregate_id="agg-risk-003",
        client_order_id="client-risk-003",
        account_id="PAPER-001",
        order_type="LIMIT",
        time_in_force="DAY",
        legs=(
            PreTradeRiskLeg(
                leg_id="leg-1",
                symbol="AAPL_SHORT_CALL",
                asset_class="OPTION",
                side="SELL_TO_OPEN",
                quantity=1,
                price=4.0,
                multiplier=100,
                strike=220.0,
                option_type="CALL",
                expiration="2026-08-21",
                metadata={"underlying_symbol": "AAPL"},
            ),
        ),
    )
    undefined = undefined_service.evaluate(naked_short, account)
    assert not undefined.allowed
    assert "UNDEFINED_RISK" in undefined.rejection_reasons
    assert undefined.exposure is not None
    assert not undefined.exposure.defined_risk

    missing_account = service.evaluate(long_call, None)
    assert not missing_account.allowed
    assert "ACCOUNT_PROFILE" in missing_account.rejection_reasons

    aggregate = CanonicalOrderAggregate(
        aggregate_id="agg-canonical-risk",
        client_order_id="client-canonical-risk",
        account_id="PAPER-001",
        idempotency_key="idem-canonical-risk",
        order_type="LIMIT",
        time_in_force="DAY",
        legs=(
            CanonicalOrderLeg(
                leg_id="leg-1",
                symbol="AAPL_CALL",
                asset_class="OPTION",
                side="BUY_TO_OPEN",
                quantity=1,
                position_effect="OPEN",
                metadata={
                    "multiplier": 100,
                    "strike": 200.0,
                    "option_type": "CALL",
                    "expiration": "2026-08-21",
                    "underlying_symbol": "AAPL",
                },
            ),
        ),
        state="ROUTED",
        version=3,
        total_quantity=1,
        filled_quantity=0,
        remaining_quantity=1,
        limit_price=5.0,
    )
    mapped = canonical_order_to_risk_request(
        aggregate,
        {"leg-1": 5.0},
    )
    mapped_decision = service.evaluate(mapped, account)
    assert mapped_decision.allowed
    assert mapped.aggregate_id == aggregate.aggregate_id

    payload = dumps(mapped_decision)
    assert '"recommendation": "APPROVE"' in payload
    assert '"gross_premium": 500.0' in payload

    print(
        "All pre-trade risk contracts, policy profiles, and "
        "order-level validation assertions passed."
    )


if __name__ == "__main__":
    main()
