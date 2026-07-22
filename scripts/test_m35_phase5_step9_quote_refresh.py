from trading_ai.scanner.dashboard.paper_trade_preparation_service import (
    PaperTradePreparationService,
)


def main() -> None:
    decision = {
        "symbol": "AMZN",
        "direction": "CALL",
        "decision": "APPROVE",
        "selected_strategy": {
            "strategy_id": "AMZN:2026-08-21:CALL:270-275:VERTICAL",
            "symbol": "AMZN",
            "direction": "CALL",
            "strategy_type": "BULL_CALL_SPREAD",
            "expiry": "2026-08-21",
            "debit": 1.16,
            "legs": [
                {
                    "symbol": "AMZN",
                    "expiry": "2026-08-21",
                    "strike": 270,
                    "option_type": "CALL",
                    "action": "BUY",
                    "quantity": 1,
                },
                {
                    "symbol": "AMZN",
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
            "bid": 5.40,
            "ask": 5.60,
        },
        {
            "underlying_symbol": "AMZN",
            "expiry": "2026-08-21",
            "strike": 275,
            "option_type": "CALL",
            "bid": 4.30,
            "ask": 4.50,
        },
    ]

    record = PaperTradePreparationService().prepare(
        decision,
        quotes,
    )

    assert record.paper_trade_ready is True
    assert record.decision == "READY"
    assert round(record.refreshed_debit or 0.0, 2) == 1.30
    assert record.paper_trade_payload is not None

    print(
        "Milestone 35 Phase 5 Step 9 quote-refresh assertions passed."
    )


if __name__ == "__main__":
    main()
