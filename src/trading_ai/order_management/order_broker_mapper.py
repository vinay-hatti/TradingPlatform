from __future__ import annotations

from trading_ai.broker.broker_order_profile import BrokerOrderLeg, BrokerOrderRequest

from .order_profile import CanonicalOrderAggregate


def canonical_to_broker_order(
    aggregate: CanonicalOrderAggregate,
    instrument_mappings: dict[str, object],
) -> BrokerOrderRequest:
    legs = []
    for leg in aggregate.legs:
        mapping = instrument_mappings.get(leg.leg_id)
        if mapping is None:
            raise ValueError(f"Missing instrument mapping for leg {leg.leg_id}")
        legs.append(
            BrokerOrderLeg(
                leg_id=leg.leg_id,
                instrument=mapping,
                side=leg.side,
                quantity=leg.quantity,
                position_effect=leg.position_effect,
                ratio=leg.ratio,
                metadata=dict(leg.metadata),
            )
        )

    return BrokerOrderRequest(
        client_order_id=aggregate.client_order_id,
        account_id=aggregate.account_id,
        order_type=aggregate.order_type,
        time_in_force=aggregate.time_in_force,
        legs=tuple(legs),
        limit_price=aggregate.limit_price,
        stop_price=aggregate.stop_price,
        outside_regular_hours=aggregate.outside_regular_hours,
        idempotency_key=aggregate.idempotency_key,
        strategy_name=aggregate.strategy_name,
        metadata={
            **aggregate.metadata,
            "canonical_aggregate_id": aggregate.aggregate_id,
            "canonical_aggregate_version": aggregate.version,
        },
    )
