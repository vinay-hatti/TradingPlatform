from trading_ai.scanner.dashboard.candidate_inspection_service import (
    CandidateInspectionService,
)


def main() -> None:
    records = [
        {
            "symbol": "AMZN",
            "institutional_score": 91,
            "probability_of_profit": "72%",
            "direction": "CALL",
            "strategy_type": "BULL_CALL_SPREAD",
            "liquidity_score": 88,
            "open_interest": 2500,
            "volume": 900,
            "spread_pct": "6%",
            "warnings": ["EARNINGS_WITHIN_30_DAYS"],
        },
        {
            "symbol": "LLY",
            "institutional_score": 84,
            "direction": "PUT",
        },
    ]

    profile = CandidateInspectionService().inspect(records, "amzn")
    assert profile.symbol == "AMZN"
    assert profile.institutional_score == 91.0
    assert profile.probability_of_profit == 0.72
    assert profile.spread_pct == 0.06
    assert profile.direction == "CALL"
    assert profile.warnings == ("EARNINGS_WITHIN_30_DAYS",)
    assert "--symbol" in profile.option_chain_command
    assert "AMZN" in profile.option_chain_command

    print(
        "Milestone 35 Phase 5 Step 5 candidate-inspection assertions passed."
    )


if __name__ == "__main__":
    main()
