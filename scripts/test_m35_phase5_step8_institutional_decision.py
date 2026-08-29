from trading_ai.scanner.dashboard.institutional_decision_profile import (
    InstitutionalDecisionPolicy,
)
from trading_ai.scanner.dashboard.institutional_decision_service import (
    InstitutionalDecisionHandoffService,
)


def main() -> None:
    payload = {
        "symbol": "AMZN",
        "direction": "CALL",
        "warnings": [],
        "ranked_strategies": [
            {
                "strategy_id": "AMZN:2026-08-21:CALL:220-225:VERTICAL",
                "symbol": "AMZN",
                "direction": "CALL",
                "expiry": "2026-08-21",
                "strategy_type": "BULL_CALL_SPREAD",
                "institutional_score": 72.0,
                "liquidity_score": 88.0,
                "probability_proxy": 0.52,
                "reward_risk_ratio": 1.8,
                "max_loss": 2.0,
                "max_profit": 3.6,
                "breakeven": 222.0,
                "debit": 2.0,
                "credit": None,
                "quote_quality": "COMPLETE",
                "warnings": [],
                "legs": [],
            }
        ],
    }

    record = InstitutionalDecisionHandoffService().evaluate(
        payload
    )
    assert record.decision == "APPROVE"
    assert record.selected_strategy_id is not None
    assert record.paper_trade_ready is True
    assert record.approved_candidates == 1

    print(
        "Milestone 35 Phase 5 Step 8 institutional-decision assertions passed."
    )


if __name__ == "__main__":
    main()
