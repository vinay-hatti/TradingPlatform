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
        "warnings": [
            "HISTORICAL_QUOTE_POLICY_ACTIVE"
        ],
        "ranked_strategies": [
            {
                "strategy_id": "AMZN:HISTORICAL",
                "symbol": "AMZN",
                "direction": "CALL",
                "expiry": "2026-08-21",
                "strategy_type": "BULL_CALL_SPREAD",
                "institutional_score": 55.7777,
                "liquidity_score": 100.0,
                "probability_proxy": 0.295,
                "reward_risk_ratio": 3.31,
                "max_loss": 1.16,
                "max_profit": 3.84,
                "breakeven": 271.16,
                "debit": 1.16,
                "credit": None,
                "quote_quality": "HISTORICAL_LAST_ONLY",
                "warnings": [
                    "INCOMPLETE_SPREAD_QUOTES"
                ],
                "legs": [],
            }
        ],
    }

    strict = InstitutionalDecisionHandoffService().evaluate(
        payload
    )
    assert strict.decision == "REJECT"
    assert (
        strict.rejection_summary["COMPLETE_QUOTES_REQUIRED"]
        == 1
    )

    research = InstitutionalDecisionHandoffService().evaluate(
        payload,
        policy=InstitutionalDecisionPolicy(
            allow_historical_quotes=True
        ),
    )
    assert research.decision == "APPROVE"
    assert research.paper_trade_ready is False
    assert (
        "QUOTE_REFRESH_REQUIRED_BEFORE_PAPER_TRADE"
        in research.warnings
    )

    print(
        "Milestone 35 Phase 5 Step 8 historical-governance assertions passed."
    )


if __name__ == "__main__":
    main()
