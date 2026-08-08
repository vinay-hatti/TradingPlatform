from __future__ import annotations
from sqlalchemy import Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from trading_ai.database.base import Base

class PortfolioRiskSnapshotModel(Base):
    __tablename__='portfolio_risk_allocation_snapshots'
    snapshot_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    portfolio_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    snapshot_timestamp:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    broker_publication_id:Mapped[str|None]=mapped_column(String(128),index=True)
    status:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    health_score:Mapped[float]=mapped_column(Float,nullable=False)
    net_liquidation:Mapped[float]=mapped_column(Float,nullable=False)
    buying_power:Mapped[float]=mapped_column(Float,nullable=False)
    capital_committed:Mapped[float]=mapped_column(Float,nullable=False)
    open_risk:Mapped[float]=mapped_column(Float,nullable=False)
    var_95:Mapped[float]=mapped_column(Float,nullable=False)
    expected_shortfall_95:Mapped[float]=mapped_column(Float,nullable=False)
    portfolio_heat_pct:Mapped[float]=mapped_column(Float,nullable=False)
    concentration_score:Mapped[float]=mapped_column(Float,nullable=False)
    diversification_score:Mapped[float]=mapped_column(Float,nullable=False)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False)

class PortfolioFitAssessmentModel(Base):
    __tablename__='portfolio_fit_assessments'
    __table_args__=(UniqueConstraint('portfolio_id','candidate_id','risk_snapshot_id',name='uq_m64_fit_candidate_snapshot'),)
    assessment_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    portfolio_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    candidate_id:Mapped[str]=mapped_column(String(160),nullable=False,index=True)
    risk_snapshot_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    symbol:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    portfolio_fit_score:Mapped[float]=mapped_column(Float,nullable=False,index=True)
    recommended_quantity:Mapped[int]=mapped_column(Integer,nullable=False)
    recommended_capital:Mapped[float]=mapped_column(Float,nullable=False)
    decision:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    assessed_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False)

class PortfolioStressSnapshotModel(Base):
    __tablename__='portfolio_stress_allocation_snapshots'
    stress_snapshot_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    portfolio_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    risk_snapshot_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    generated_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    worst_scenario:Mapped[str]=mapped_column(String(64),nullable=False)
    worst_loss:Mapped[float]=mapped_column(Float,nullable=False)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False)

class PortfolioDecisionIntelligenceModel(Base):
    __tablename__ = 'portfolio_decision_intelligence_snapshots'
    __table_args__ = (UniqueConstraint('portfolio_id','opportunity_id','risk_snapshot_id',name='uq_m64_portfolio_decision_risk'),)
    decision_intelligence_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    institutional_decision_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    risk_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    portfolio_fit_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    opportunity_cost_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    final_portfolio_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    recommended_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_capital: Mapped[float] = mapped_column(Float, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rank: Mapped[int | None] = mapped_column(Integer, index=True)
    state_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

class PortfolioCorrelationSnapshotModel(Base):
    __tablename__ = 'portfolio_correlation_snapshots'
    correlation_snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    generated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

class PortfolioRiskBudgetSnapshotModel(Base):
    __tablename__ = 'portfolio_risk_budget_snapshots'
    __table_args__ = (UniqueConstraint('portfolio_id','risk_snapshot_id',name='uq_m64_budget_risk'),)
    budget_snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    generated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    utilization_pct: Mapped[float] = mapped_column(Float, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

class PortfolioOptimizationSnapshotModel(Base):
    __tablename__ = 'portfolio_optimization_snapshots'
    __table_args__ = (UniqueConstraint('portfolio_id','risk_snapshot_id',name='uq_m64_optimizer_risk'),)
    optimization_snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    generated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    objective_score: Mapped[float] = mapped_column(Float, nullable=False)
    selected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_capital: Mapped[float] = mapped_column(Float, nullable=False)
    state_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

class PortfolioRecommendationModel(Base):
    __tablename__ = 'portfolio_action_recommendations'
    __table_args__ = (UniqueConstraint('portfolio_id','risk_snapshot_id','action_key',name='uq_m64_action_risk_key'),)
    recommendation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action_key: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(32), index=True)
    priority: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

class PortfolioIntelligencePublicationModel(Base):
    __tablename__ = 'portfolio_allocation_publications'
    __table_args__ = (UniqueConstraint('portfolio_id','publication_name',name='uq_m64_portfolio_publication'),)
    publication_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    publication_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    portfolio_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    optimization_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    published_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
