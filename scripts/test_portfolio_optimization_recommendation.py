from trading_ai.strategy_engine.portfolio_optimization_frontier_profile import PortfolioOptimizationFrontierPoint, PortfolioOptimizationFrontierProfile
from trading_ai.strategy_engine.portfolio_optimization_recommendation_service import PortfolioOptimizationRecommendationService
from trading_ai.strategy_engine.portfolio_optimization_recommendation_serialization import portfolio_optimization_recommendation_to_dict


def main():
    point=PortfolioOptimizationFrontierPoint(point_id="FRONTIER_001", maximum_exposure_pct=0.30, maximum_risk_pct=0.12, maximum_concentration_pct=0.25, selected_count=4, allocated_capital=30000.0, exposure_pct=0.30, maximum_loss=9000.0, risk_pct=0.09, expected_profit=4500.0, expected_return_pct=0.15, objective_score=84.0, diversification_score=82.0, concentration_score=78.0, greek_utilization_score=88.0, optimization_grade="B", risk_severity="MODERATE", allowed=True, valid=True, pareto_efficient=True)
    profile=PortfolioOptimizationFrontierProfile(initial_capital=100000.0, candidate_count=6, point_count=1, valid_point_count=1, pareto_point_count=1, best_point_id="FRONTIER_001", best_objective_score=84.0, best_expected_return_pct=0.15, lowest_risk_pct=0.09, highest_expected_return_pct=0.15, objective_range=0.0, expected_return_range=0.0, risk_range=0.0, selection_stability_score=88.0, allocation_stability_score=91.0, constraint_sensitivity_score=22.0, frontier_score=86.0, frontier_grade="A", risk_severity="MODERATE", allowed=True, valid=True, points=[point], pareto_points=[point])
    rec=PortfolioOptimizationRecommendationService().recommend(profile)
    assert rec.valid and rec.allowed
    assert rec.source_point_id == "FRONTIER_001"
    assert rec.recommended_policy.maximum_portfolio_exposure_pct == 0.30
    assert rec.recommended_policy.maximum_total_risk_pct == 0.12
    assert portfolio_optimization_recommendation_to_dict(rec)["source_point_id"] == "FRONTIER_001"
    print("All portfolio-optimization recommendation assertions passed.")

if __name__ == "__main__": main()
