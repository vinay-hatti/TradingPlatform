from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.scanner.dashboard.paper_trade_lifecycle_service import (
    PaperTradeLifecycleService,
)


def _payload() -> dict:
    return {
        "symbol": "AMZN",
        "direction": "CALL",
        "strategy_id": (
            "AMZN:2026-08-21:CALL:270.0-275.0:VERTICAL"
        ),
        "strategy_type": "BULL_CALL_SPREAD",
        "paper_trade_ready": True,
        "paper_trade_payload": {
            "strategy_id": (
                "AMZN:2026-08-21:CALL:270.0-275.0:VERTICAL"
            ),
            "symbol": "AMZN",
            "direction": "CALL",
            "strategy_type": "BULL_CALL_SPREAD",
            "expiry": "2026-08-21",
            "limit_debit": 1.30,
            "max_profit": 3.70,
            "max_loss": 1.30,
            "breakeven": 271.30,
            "reward_risk_ratio": 2.846153846,
            "legs": [
                {
                    "symbol": "AMZN",
                    "expiry": "2026-08-21",
                    "strike": 270.0,
                    "option_type": "CALL",
                    "action": "BUY",
                    "quantity": 1,
                    "bid": 5.40,
                    "ask": 5.60,
                },
                {
                    "symbol": "AMZN",
                    "expiry": "2026-08-21",
                    "strike": 275.0,
                    "option_type": "CALL",
                    "action": "SELL",
                    "quantity": 1,
                    "bid": 4.30,
                    "ask": 4.50,
                },
            ],
        },
    }


def main() -> None:
    with TemporaryDirectory() as directory:
        registry = Path(directory) / "registry.json"
        service = PaperTradeLifecycleService()

        first = service.submit(
            _payload(),
            registry_path=registry,
            fill_mode="IMMEDIATE",
        )
        assert first.order.status == "FILLED"
        assert first.position is not None
        assert first.position.status == "OPEN"
        assert first.duplicate_submission is False
        assert [
            event.event_type for event in first.events
        ] == [
            "ORDER_SUBMITTED",
            "ORDER_FILLED",
            "POSITION_OPENED",
        ]

        duplicate = service.submit(
            _payload(),
            registry_path=registry,
            fill_mode="IMMEDIATE",
        )
        assert duplicate.order.order_id == first.order.order_id
        assert duplicate.duplicate_submission is True

    print(
        "Milestone 35 Phase 5 Step 10 lifecycle assertions passed."
    )


if __name__ == "__main__":
    main()
