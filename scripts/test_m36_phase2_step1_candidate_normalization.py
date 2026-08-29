from trading_ai.portfolio_management.construction_service import PortfolioCandidateNormalizer


def main():
    candidate = PortfolioCandidateNormalizer().normalize({
        "ranked_opportunity": {
            "ranking_score": 88,
            "raw_ranking_score": 90,
            "allowed": True,
            "selected": True,
            "action": "TRADE",
            "opportunity": {
                "symbol": "aapl",
                "strategy": "bull_call_spread",
                "direction": "call",
                "strategy_score": 84,
                "portfolio_fit_score": 76,
                "capital_required": 250,
                "maximum_loss": 250,
                "expected_profit": 180,
                "expected_return_pct": 72,
                "readiness": "ready",
                "recommendation": "trade",
            },
        }
    })
    assert candidate.symbol == "AAPL"
    assert candidate.strategy == "BULL_CALL_SPREAD"
    assert candidate.ranking_score == 88
    assert candidate.capital_required == 250
    assert candidate.candidate_id.startswith("CANDIDATE-")
    print("Milestone 36 Phase 2 Step 1 candidate-normalization assertions passed.")


if __name__ == "__main__":
    main()
