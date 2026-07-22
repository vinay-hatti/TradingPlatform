from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.paper_trade_lifecycle_service import (
    PaperTradeLifecycleService,
)


def main() -> None:
    payload = {
        "symbol": "AMZN",
        "direction": "CALL",
        "strategy_id": "AMZN:PENDING",
        "strategy_type": "BULL_CALL_SPREAD",
        "paper_trade_ready": True,
        "paper_trade_payload": {
            "strategy_id": "AMZN:PENDING",
            "symbol": "AMZN",
            "direction": "CALL",
            "strategy_type": "BULL_CALL_SPREAD",
            "expiry": "2026-08-21",
            "limit_debit": 1.25,
            "max_profit": 3.75,
            "max_loss": 1.25,
            "breakeven": 271.25,
            "reward_risk_ratio": 3.0,
            "legs": [
                {
                    "symbol": "AMZN",
                    "expiry": "2026-08-21",
                    "strike": 270,
                    "option_type": "CALL",
                    "action": "BUY",
                    "quantity": 1,
                    "bid": 5.40,
                    "ask": 5.60,
                },
                {
                    "symbol": "AMZN",
                    "expiry": "2026-08-21",
                    "strike": 275,
                    "option_type": "CALL",
                    "action": "SELL",
                    "quantity": 1,
                    "bid": 4.35,
                    "ask": 4.50,
                },
            ],
        },
    }

    with TemporaryDirectory() as directory:
        record = PaperTradeLifecycleService().submit(
            payload,
            registry_path=Path(directory) / "registry.json",
            fill_mode="PENDING",
        )
        assert record.order.status == "SUBMITTED"
        assert record.position is None
        assert [
            event.event_type for event in record.events
        ] == ["ORDER_SUBMITTED"]

    print(
        "Milestone 35 Phase 5 Step 10 pending-order assertions passed."
    )


if __name__ == "__main__":
    main()
