from trading_ai.scanner.dashboard.paper_trade_preparation_service import (
    PaperTradePreparationService,
)


def main() -> None:
    decision = {
        "symbol": "AMZN",
        "direction": "CALL",
        "decision": "APPROVE",
        "selected_strategy": {
            "strategy_id": "AMZN:TEST",
            "symbol": "AMZN",
            "direction": "CALL",
            "strategy_type": "BULL_CALL_SPREAD",
            "expiry": "2026-08-21",
            "debit": 1.16,
            "legs": [
                {
                    "expiry": "2026-08-21",
                    "strike": 270,
                    "option_type": "CALL",
                    "action": "BUY",
                    "quantity": 1,
                },
                {
                    "expiry": "2026-08-21",
                    "strike": 275,
                    "option_type": "CALL",
                    "action": "SELL",
                    "quantity": 1,
                },
            ],
        },
    }
    quotes = [
        {
            "underlying_symbol": "AMZN",
            "expiry": "2026-08-21",
            "strike": 270,
            "option_type": "CALL",
            "bid": 4.0,
            "ask": 6.0,
        }
    ]

    record = PaperTradePreparationService().prepare(
        decision,
        quotes,
    )

    assert record.paper_trade_ready is False
    assert "QUOTE_NOT_FOUND" in record.rejection_reasons
    assert "COMPLETE_QUOTES_REQUIRED" in record.rejection_reasons

    print(
        "Milestone 35 Phase 5 Step 9 rejection assertions passed."
    )


if __name__ == "__main__":
    main()
