from trading_ai.strategy_engine.portfolio_optimization_policy import PortfolioOptimizationPolicy
from trading_ai.strategy_engine.portfolio_optimization_recommendation_engine import PortfolioOptimizationRecommendationEngine
from trading_ai.strategy_engine.portfolio_optimization_recommendation_policy import PortfolioOptimizationRecommendationPolicy


class PortfolioOptimizationRecommendationService:
    def __init__(self, policy: PortfolioOptimizationRecommendationPolicy | None = None, engine: PortfolioOptimizationRecommendationEngine | None = None) -> None:
        self.policy = policy or PortfolioOptimizationRecommendationPolicy()
        self.engine = engine or PortfolioOptimizationRecommendationEngine(self.policy)

    def recommend(self, frontier_profile, base_policy: PortfolioOptimizationPolicy | None = None):
        return self.engine.recommend(frontier_profile, base_policy)
