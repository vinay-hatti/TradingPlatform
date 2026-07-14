from trading_ai.strategy_engine.portfolio_risk_surface_engine import PortfolioRiskSurfaceEngine
from trading_ai.strategy_engine.risk_surface_engine import RiskSurfaceEngine
from trading_ai.strategy_engine.risk_surface_policy import RiskSurfacePolicy


class RiskSurfaceService:
    def __init__(self, policy=None, engine=None, portfolio_engine=None):
        self.policy=policy or RiskSurfacePolicy(); self.policy.validate()
        self.engine=engine or RiskSurfaceEngine(policy=self.policy)
        self.portfolio_engine=portfolio_engine or PortfolioRiskSurfaceEngine(policy=self.policy)
    def analyze_strategy(self, **kwargs): return self.engine.analyze(**kwargs)
    def analyze_portfolio(self, profiles, initial_capital, allocations=None, position_metadata=None):
        return self.portfolio_engine.analyze(profiles=profiles,initial_capital=initial_capital,allocations=allocations,position_metadata=position_metadata)
