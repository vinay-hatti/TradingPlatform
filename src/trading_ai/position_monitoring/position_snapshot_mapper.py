from __future__ import annotations

from trading_ai.paper_trading.paper_position_profile import PaperPositionProfile

from .position_monitoring_profile import RealTimePositionSnapshot


def paper_position_to_realtime_snapshot(
    position: PaperPositionProfile,
) -> RealTimePositionSnapshot:
    return RealTimePositionSnapshot(
        position_id=position.position_id,
        account_id=position.account_id,
        symbol=position.symbol,
        underlying_symbol=str(
            position.metadata.get("underlying_symbol", position.symbol)
        ),
        asset_class=position.asset_class,
        side=position.side,
        quantity=position.quantity,
        average_cost=position.average_cost,
        multiplier=position.multiplier,
        realized_pnl=position.realized_pnl,
        total_commissions=position.total_commissions,
        sector=position.metadata.get("sector"),
        strategy_name=position.metadata.get("strategy_name"),
        opened_at=position.opened_at,
        metadata={
            **position.metadata,
            "source_position_state": position.state,
            "aggregate_id": position.aggregate_id,
            "session_id": position.session_id,
        },
    )
