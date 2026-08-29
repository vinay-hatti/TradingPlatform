from trading_ai.scanner.dashboard.paper_trade_performance_service import (
    PaperTradePerformanceService,
)


def main() -> None:
    lifecycle = {
        "position": {
            "position_id": "POSITION-001",
            "order_id": "ORDER-001",
            "strategy_id": "AMZN:TEST",
            "symbol": "AMZN",
            "direction": "CALL",
            "strategy_type": "BULL_CALL_SPREAD",
            "status": "OPEN",
            "quantity": 1,
            "entry_debit": 1.30,
            "max_profit": 3.70,
            "max_loss": 1.30,
            "breakeven": 271.30,
            "reward_risk_ratio": 2.846,
            "opened_at": "2026-07-21T15:00:00+00:00",
            "closed_at": None,
            "realized_pnl": None,
            "unrealized_pnl": None,
            "legs": [],
        }
    }
    marks = [
        {
            "position_id": "POSITION-001",
            "status": "OPEN",
            "current_debit": 1.60,
            "marked_at": "2026-07-21T16:00:00+00:00",
        }
    ]

    report = PaperTradePerformanceService().evaluate(
        [lifecycle],
        marks,
    )
    assert report.summary.total_positions == 1
    assert report.summary.open_positions == 1
    assert round(
        report.summary.total_unrealized_pnl,
        2,
    ) == 30.00
    assert round(
        report.positions[0].return_pct or 0.0,
        6,
    ) == round(30.0 / 130.0, 6)

    print(
        "Milestone 35 Phase 5 Step 11 performance assertions passed."
    )


if __name__ == "__main__":
    main()
