from __future__ import annotations
from sqlalchemy import Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from trading_ai.database.base import Base

class OptionValuationSnapshotModel(Base):
    __tablename__='institutional_option_valuation_snapshots'
    __table_args__=(UniqueConstraint('contract_recommendation_id','state_hash',name='uq_m69_contract_state'),)
    snapshot_id: Mapped[str]=mapped_column(String(128),primary_key=True)
    contract_recommendation_id: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    opportunity_id: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    symbol: Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    classification: Mapped[str]=mapped_column(String(48),nullable=False,index=True)
    market_mid: Mapped[float]=mapped_column(Float,nullable=False)
    fair_value: Mapped[float]=mapped_column(Float,nullable=False)
    mispricing_pct: Mapped[float]=mapped_column(Float,nullable=False,index=True)
    edge_score: Mapped[float]=mapped_column(Float,nullable=False,index=True)
    confidence: Mapped[float]=mapped_column(Float,nullable=False)
    stability_index: Mapped[float]=mapped_column(Float,nullable=False)
    state_hash: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    snapshot_timestamp: Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    payload_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class OptionValuationPublicationModel(Base):
    __tablename__='institutional_option_valuation_publications'
    publication_id: Mapped[str]=mapped_column(String(128),primary_key=True)
    publication_name: Mapped[str]=mapped_column(String(128),nullable=False,unique=True,index=True)
    status: Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    contract_count: Mapped[int]=mapped_column(Integer,nullable=False)
    underpriced_count: Mapped[int]=mapped_column(Integer,nullable=False)
    overpriced_count: Mapped[int]=mapped_column(Integer,nullable=False)
    published_at: Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    payload_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class OptionEdgeLedgerModel(Base):
    __tablename__='institutional_option_edge_ledger'
    ledger_id: Mapped[str]=mapped_column(String(128),primary_key=True)
    contract_recommendation_id: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    opportunity_id: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    state_hash: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    observed_at: Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    payload_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class OptionValuationEventModel(Base):
    __tablename__='institutional_option_valuation_events'
    event_id: Mapped[str]=mapped_column(String(128),primary_key=True)
    symbol: Mapped[str]=mapped_column(String(32),nullable=False,index=True,default='*')
    event_type: Mapped[str]=mapped_column(String(48),nullable=False,index=True)
    event_date: Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    status: Mapped[str]=mapped_column(String(24),nullable=False,index=True,default='ACTIVE')
    expected_move_pct: Mapped[float|None]=mapped_column(Float)
    historical_move_pct: Mapped[float|None]=mapped_column(Float)
    confidence: Mapped[float]=mapped_column(Float,nullable=False,default=50.0)
    source: Mapped[str]=mapped_column(String(64),nullable=False,default='GOVERNED_REGISTRY')
    source_event_key: Mapped[str|None]=mapped_column(String(256),nullable=True)
    release_name: Mapped[str|None]=mapped_column(String(256),nullable=True)
    event_time: Mapped[str|None]=mapped_column(String(32),nullable=True)
    event_timezone: Mapped[str|None]=mapped_column(String(64),nullable=True)
    event_session: Mapped[str|None]=mapped_column(String(32),nullable=True)
    event_time_status: Mapped[str|None]=mapped_column(String(32),nullable=True)
    calendar_source: Mapped[str|None]=mapped_column(String(64),nullable=True)
    date_status: Mapped[str|None]=mapped_column(String(32),nullable=True)
    implied_move_pct: Mapped[float|None]=mapped_column(Float,nullable=True)
    forecast_move_pct: Mapped[float|None]=mapped_column(Float,nullable=True)
    historical_sample_size: Mapped[int|None]=mapped_column(Integer,nullable=True)
    calculation_method: Mapped[str|None]=mapped_column(String(96),nullable=True)
    options_snapshot_id: Mapped[str|None]=mapped_column(String(128),nullable=True)
    event_components_json: Mapped[list|None]=mapped_column(JSON,nullable=True)
    evidence_json: Mapped[dict|None]=mapped_column(JSON,nullable=True)
    source_updated_at: Mapped[str|None]=mapped_column(String(64),nullable=True)
    first_seen_at: Mapped[str|None]=mapped_column(String(64),nullable=True)
    last_seen_at: Mapped[str|None]=mapped_column(String(64),nullable=True)
    superseded_at: Mapped[str|None]=mapped_column(String(64),nullable=True)
    revision_number: Mapped[int|None]=mapped_column(Integer,nullable=True)
    meeting_start_date: Mapped[str|None]=mapped_column(String(32),nullable=True)
    meeting_end_date: Mapped[str|None]=mapped_column(String(32),nullable=True)
    content_hash: Mapped[str|None]=mapped_column(String(128),nullable=True)
    record_origin: Mapped[str|None]=mapped_column(String(32),nullable=True)
    payload_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class OptionRelativeValueSnapshotModel(Base):
    __tablename__='institutional_option_relative_value_snapshots'
    relative_value_id: Mapped[str]=mapped_column(String(128),primary_key=True)
    valuation_run_id: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    contract_recommendation_id: Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    symbol: Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    sector: Mapped[str]=mapped_column(String(96),nullable=False,index=True)
    peer_group: Mapped[str]=mapped_column(String(160),nullable=False,index=True)
    symbol_iv: Mapped[float]=mapped_column(Float,nullable=False)
    peer_median_iv: Mapped[float]=mapped_column(Float,nullable=False)
    divergence_pct: Mapped[float]=mapped_column(Float,nullable=False)
    z_score: Mapped[float]=mapped_column(Float,nullable=False)
    relationship_regime: Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    snapshot_timestamp: Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    payload_json: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
