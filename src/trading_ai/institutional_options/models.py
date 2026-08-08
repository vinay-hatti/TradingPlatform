from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from trading_ai.database.base import Base


class InstitutionalOpportunityModel(Base):
    __tablename__ = "institutional_option_opportunities"
    __table_args__ = (UniqueConstraint("stock_scanner_run_id", "stock_candidate_id", name="uq_m62_stock_candidate_lineage"),)

    opportunity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    asset_class: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    conviction: Mapped[str] = mapped_column(String(32), nullable=False)
    thesis_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    stock_publication_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    stock_scanner_run_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    stock_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    stock_state_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    option_snapshot_id: Mapped[str | None] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class OpportunityThesisModel(Base):
    __tablename__ = "institutional_option_theses"

    thesis_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    setup_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    primary_timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    invalidation_level: Mapped[float] = mapped_column(Float, nullable=False)
    entry_zone_low: Mapped[float] = mapped_column(Float, nullable=False)
    entry_zone_high: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class StrategyCandidateModel(Base):
    __tablename__ = "institutional_option_strategy_candidates"
    __table_args__ = (UniqueConstraint("opportunity_id", "strategy", name="uq_m62_opportunity_strategy"),)

    strategy_candidate_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    disposition: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    eligibility_score: Mapped[float] = mapped_column(Float, nullable=False)
    strategy_score: Mapped[float | None] = mapped_column(Float)
    complexity: Mapped[str] = mapped_column(String(32), nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class StrategyComparisonModel(Base):
    __tablename__ = "institutional_option_strategy_comparisons"

    comparison_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    selected_strategy_candidate_id: Mapped[str | None] = mapped_column(String(128), index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class ContractRecommendationModel(Base):
    __tablename__ = "institutional_option_contract_recommendations"

    contract_recommendation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    strategy_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    option_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    executable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    liquidity_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class ExecutionRecommendationModel(Base):
    __tablename__ = "institutional_option_execution_recommendations"

    execution_recommendation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    strategy_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    contract_recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    underlying_stop: Mapped[float] = mapped_column(Float, nullable=False)
    trailing_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    ready_for_trade_builder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class OpportunityOutcomeAttributionModel(Base):
    __tablename__ = "institutional_option_outcome_attributions"

    attribution_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    strategy_candidate_id: Mapped[str | None] = mapped_column(String(128), index=True)
    contract_recommendation_id: Mapped[str | None] = mapped_column(String(128), index=True)
    outcome: Mapped[str | None] = mapped_column(String(32), index=True)
    realized_return_pct: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String(64), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class InstitutionalOpportunityAuditModel(Base):
    __tablename__ = "institutional_option_opportunity_audit"

    audit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    previous_state: Mapped[str | None] = mapped_column(String(32))
    new_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    event_timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class StrategyValuationModel(Base):
    __tablename__ = "institutional_option_strategy_valuations"
    __table_args__ = (UniqueConstraint("opportunity_id", "strategy_candidate_id", name="uq_m62_strategy_valuation"),)

    valuation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    strategy_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    strategy_score: Mapped[float] = mapped_column(Float, nullable=False)
    calibrated_probability: Mapped[float | None] = mapped_column(Float)
    expected_value: Mapped[float | None] = mapped_column(Float)
    expected_return_on_risk: Mapped[float | None] = mapped_column(Float)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class PositionManagementSnapshotModel(Base):
    __tablename__ = "institutional_option_management_snapshots"

    management_snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    strategy_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    thesis_integrity: Mapped[float] = mapped_column(Float, nullable=False)
    position_health: Mapped[float] = mapped_column(Float, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    trailing_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

class InstitutionalOptionHandoffModel(Base):
    __tablename__ = "institutional_option_handoffs"
    __table_args__ = (UniqueConstraint("opportunity_id", "account_id", "strategy_candidate_id", name="uq_m62_handoff_source"),)

    handoff_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    strategy_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    contract_recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    execution_recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    trade_plan_id: Mapped[str | None] = mapped_column(String(128), index=True)
    execution_intent_id: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    overrides_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    lineage_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)

class InstitutionalOptionOutcomeObservationModel(Base):
    __tablename__ = "institutional_option_outcome_observations"

    observation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    strategy_candidate_id: Mapped[str | None] = mapped_column(String(128), index=True)
    setup_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    market_regime: Mapped[str | None] = mapped_column(String(64), index=True)
    management_policy: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    predicted_probability: Mapped[float | None] = mapped_column(Float)
    realized_return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    exit_reason: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entry_timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exit_timestamp: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class InstitutionalOptionLearningSnapshotModel(Base):
    __tablename__ = "institutional_option_learning_snapshots"

    learning_snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_value: Mapped[str | None] = mapped_column(String(128), index=True)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    win_rate: Mapped[float | None] = mapped_column(Float)
    expectancy_pct: Mapped[float | None] = mapped_column(Float)
    brier_score: Mapped[float | None] = mapped_column(Float)
    expected_calibration_error: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

class InstitutionalDecisionSnapshotModel(Base):
    __tablename__ = "institutional_option_decision_snapshots"

    decision_snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    strategy_candidate_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    contract_recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    valuation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    execution_recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    management_snapshot_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    institutional_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    calibrated_probability: Mapped[float | None] = mapped_column(Float)
    expected_value: Mapped[float | None] = mapped_column(Float)
    capital_required: Mapped[float | None] = mapped_column(Float)
    selected_strategy: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
