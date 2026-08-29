from __future__ import annotations
import tempfile
from pathlib import Path

from trading_ai.paper_trading.paper_execution_profile import (
    PaperExecutionRecord,
    PaperFillProfile,
)
from trading_ai.paper_trading.paper_position_repository import (
    JsonPaperPositionRepository,
)
from trading_ai.paper_trading.paper_position_serialization import dumps
from trading_ai.paper_trading.paper_position_service import PaperPositionService
from trading_ai.paper_trading.paper_trading_profile import PaperTradingSessionProfile
from trading_ai.paper_trading.paper_trading_runtime_repository import (
    JsonPaperTradingRuntimeRepository,
)
from trading_ai.paper_trading.paper_trading_session_service import (
    PaperTradingSessionService,
)

def make_fill(fill_id, side, quantity, price, commission):
    return PaperFillProfile(
        fill_id=fill_id,
        execution_key="exec-1",
        aggregate_id="agg-1",
        client_order_id="client-1",
        leg_id="leg-1",
        symbol="AAPL_CALL_200",
        side=side,
        quantity=quantity,
        fill_price=price,
        reference_price=price,
        slippage_amount=0.0,
        slippage_bps=0.0,
        commission=commission,
        latency_ms=100,
        filled_at="2026-07-16T15:00:00+00:00",
    )

def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        runtime_repo = JsonPaperTradingRuntimeRepository(root / "runtime.json")
        session_service = PaperTradingSessionService(repository=runtime_repo)
        profile = PaperTradingSessionProfile(
            session_id="paper-session-004",
            account_id="PAPER-001",
            environment="paper",
            strategy_names=("LONG_CALL",),
            symbols=("AAPL_CALL_200",),
            cycle_interval_seconds=60,
            starting_capital=100000.0,
        )
        assert session_service.create(profile)[0].allowed

        fill = make_fill("fill-open", "BUY_TO_OPEN", 2, 5.0, 1.30)
        record = PaperExecutionRecord(
            execution_key="exec-1",
            session_id=profile.session_id,
            cycle_id="cycle-1",
            aggregate_id="agg-1",
            client_order_id="client-1",
            account_id="PAPER-001",
            order_type="LIMIT",
            time_in_force="DAY",
            status="FILLED",
            requested_quantity=2,
            filled_quantity=2,
            remaining_quantity=0,
            average_fill_price=5.0,
            gross_value=10.0,
            commissions=1.30,
            net_cash_flow=-11.30,
            latency_ms=100,
            fills=(fill,),
        )

        position_repo = JsonPaperPositionRepository(root / "positions.json")
        service = PaperPositionService(
            repository=position_repo,
            runtime_repository=runtime_repo,
        )
        opened = service.process_execution(
            record,
            asset_class="OPTION",
            multiplier=100,
        )
        assert opened.allowed
        position = opened.position
        assert position is not None
        assert position.quantity == 2
        assert position.average_cost == 5.0
        assert position.cost_basis == 1000.0
        assert position.state == "OPEN"
        assert len(position.lots) == 1

        marked = service.mark(position.position_id, 6.5)
        assert marked.unrealized_pnl == 300.0
        assert marked.market_value == 1300.0
        assert marked.high_water_mark == 6.5

        exit_decision = service.evaluate_exit(position.position_id)
        assert exit_decision.recommendation == "EXIT"
        assert exit_decision.exit_signal is not None
        assert exit_decision.exit_signal.reason == "PROFIT_TARGET"
        assert exit_decision.exit_signal.action == "SELL_TO_CLOSE"

        close_fill = make_fill("fill-close", "SELL_TO_CLOSE", 2, 6.5, 1.30)
        closed = service.close(position.position_id, close_fill)
        assert closed.state == "CLOSED"
        assert closed.quantity == 0
        assert closed.realized_pnl == 298.7
        assert closed.closed_at is not None

        runtime = runtime_repo.require(profile.session_id)
        assert runtime.open_positions == 0
        assert runtime.realized_pnl == 298.7

        # Negative mark produces an adjustment proposal.
        second_record = PaperExecutionRecord(
            **{
                **record.__dict__,
                "execution_key": "exec-2",
                "aggregate_id": "agg-2",
                "client_order_id": "client-2",
                "fills": (
                    PaperFillProfile(
                        **{
                            **fill.__dict__,
                            "fill_id": "fill-open-2",
                            "execution_key": "exec-2",
                            "aggregate_id": "agg-2",
                            "client_order_id": "client-2",
                        }
                    ),
                ),
            }
        )
        second = service.process_execution(
            second_record,
            asset_class="OPTION",
            multiplier=100,
        )
        assert second.position is not None
        second_mark = service.mark(second.position.position_id, 4.0)
        assert second_mark.unrealized_pnl == -200.0
        adjustment = service.evaluate_adjustment(second.position.position_id)
        assert adjustment.recommendation == "ADJUST"
        assert adjustment.adjustment is not None
        assert adjustment.adjustment.adjustment_type == "REDUCE_SIZE"

        stop = service.evaluate_exit(second.position.position_id)
        assert stop.recommendation == "EXIT"
        assert stop.exit_signal is not None
        assert stop.exit_signal.reason == "STOP_LOSS"

        reloaded = JsonPaperPositionRepository(
            root / "positions.json"
        ).get(position.position_id)
        assert reloaded is not None
        assert reloaded.state == "CLOSED"

        payload = dumps(closed)
        assert '"state": "CLOSED"' in payload
        assert '"realized_pnl": 298.7' in payload

    print(
        "All paper position lifecycle, cost-basis, P&L, automated-exit, "
        "and adjustment assertions passed."
    )

if __name__ == "__main__":
    main()
