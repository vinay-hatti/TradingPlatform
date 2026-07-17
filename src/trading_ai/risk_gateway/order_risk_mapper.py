from __future__ import annotations

from trading_ai.order_management.order_profile import CanonicalOrderAggregate

from .pretrade_risk_profile import PreTradeRiskLeg, PreTradeRiskRequest


def canonical_order_to_risk_request(
    aggregate: CanonicalOrderAggregate,
    market_prices: dict[str, float],
) -> PreTradeRiskRequest:
    legs = []
    for leg in aggregate.legs:
        price = market_prices.get(leg.leg_id)
        multiplier = int(
            leg.metadata.get(
                "multiplier",
                100 if leg.asset_class.upper() == "OPTION" else 1,
            )
        )
        legs.append(
            PreTradeRiskLeg(
                leg_id=leg.leg_id,
                symbol=leg.symbol,
                asset_class=leg.asset_class,
                side=leg.side,
                quantity=leg.quantity,
                price=price,
                multiplier=multiplier,
                strike=leg.metadata.get("strike"),
                option_type=leg.metadata.get("option_type"),
                expiration=leg.metadata.get("expiration"),
                position_effect=leg.position_effect,
                metadata=dict(leg.metadata),
            )
        )

    return PreTradeRiskRequest(
        aggregate_id=aggregate.aggregate_id,
        client_order_id=aggregate.client_order_id,
        account_id=aggregate.account_id,
        order_type=aggregate.order_type,
        time_in_force=aggregate.time_in_force,
        legs=tuple(legs),
        limit_price=aggregate.limit_price,
        stop_price=aggregate.stop_price,
        strategy_name=aggregate.strategy_name,
        metadata={
            **aggregate.metadata,
            "aggregate_version": aggregate.version,
        },
    )
