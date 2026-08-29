from trading_ai.portfolio_management.construction_policy import PortfolioConstructionGovernancePolicy
from trading_ai.portfolio_management.construction_profile import PortfolioConstructionPolicyProfile
from trading_ai.portfolio_management.construction_service import PortfolioCandidateNormalizer


def main():
    policy = PortfolioConstructionGovernancePolicy(PortfolioConstructionPolicyProfile())
    candidate = PortfolioCandidateNormalizer().normalize({
        "symbol": "AMZN", "strategy": "BULL_CALL_SPREAD", "direction": "CALL",
        "ranking_score": 90, "strategy_score": 90, "portfolio_fit_score": 90,
        "capital_required": 200, "maximum_loss": 200, "allowed": True,
        "selected": True, "readiness": "READY", "recommendation": "TRADE",
    })
    existing = [{"symbol": "AMZN", "strategy_type": "BULL_CALL_SPREAD", "direction": "CALL", "status": "OPEN", "sector": "CONSUMER", "correlation_group": "MEGA_CAP"}]
    reasons = policy.candidate_rejections(candidate, existing)
    assert "SYMBOL_POSITION_LIMIT_REACHED" in reasons
    print("Milestone 36 Phase 2 Step 1 constraint-governance assertions passed.")


if __name__ == "__main__":
    main()
