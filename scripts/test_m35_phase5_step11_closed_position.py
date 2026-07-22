from trading_ai.scanner.dashboard.paper_trade_performance_service import (
    PaperTradePerformanceService,
)


def main() -> None:
    lifecycle = {
        "position": {
            "position_id": "POSITION-002",
            "strategy_id": "AMZN:CLOSED",
            "symbol": "AMZN",
            "status": "OPEN",
            "quantity": 2,
            "entry_debit": 1.25,
        }
    }
    marks = [
        {
            "position_id": "POSITION-002",
            "status": "CLOSED",
            "exit_debit": 1.75,
            "closed_at": "2026-07-22T15:00:00+00:00",
        }
    ]

    report = PaperTradePerformanceService().evaluate(
        [lifecycle],
        marks,
    )
    position = report.positions[0]
    assert position.status == "CLOSED"
    assert position.realized_pnl == 100.0
    assert report.summary.winning_positions == 1
    assert report.summary.win_rate == 1.0

    print(
        "Milestone 35 Phase 5 Step 11 closed-position assertions passed."
    )


if __name__ == "__main__":
    main()
