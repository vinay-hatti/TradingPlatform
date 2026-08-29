from trading_ai.database.base import Base
from trading_ai.portfolio_risk_management.database_models import PortfolioRiskAssessmentModel, PortfolioRiskBreachModel, PortfolioStressResultModel

assert PortfolioRiskAssessmentModel.__tablename__ in Base.metadata.tables
assert PortfolioRiskBreachModel.__tablename__ in Base.metadata.tables
assert PortfolioStressResultModel.__tablename__ in Base.metadata.tables
print("Milestone 37 database model assertions passed.")
