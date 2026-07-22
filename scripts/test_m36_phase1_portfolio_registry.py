from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.portfolio_management.service import PortfolioRegistryService


def main() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "registry.json"
        service = PortfolioRegistryService(path)
        initial = service.initialize("Institutional Portfolio", 100000.0)
        assert initial.cash_balance == 100000.0
        opened = service.register_position(
            symbol="AMZN",
            strategy_id="AMZN:2026-08-21:CALL:270-275:VERTICAL",
            strategy_type="BULL_CALL_SPREAD",
            direction="CALL",
            quantity=1,
            entry_price=1.30,
            capital_committed=130.0,
            maximum_loss=130.0,
            maximum_profit=370.0,
            sector="CONSUMER CYCLICAL",
        )
        assert opened.open_position_count == 1
        position_id = opened.positions[0].position_id
        marked = service.mark_position(position_id, 1.50)
        assert marked.total_unrealized_pnl == 20.0
        closed = service.close_position(position_id, 1.60)
        assert closed.open_position_count == 0
        assert closed.closed_position_count == 1
        assert closed.total_realized_pnl == 30.0
        assert closed.cash_balance == 100030.0
        assert closed.net_liquidation_value == 100030.0
    print("Milestone 36 Phase 1 portfolio registry assertions passed.")


if __name__ == "__main__":
    main()
