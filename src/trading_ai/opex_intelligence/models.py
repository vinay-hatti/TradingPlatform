from __future__ import annotations
from sqlalchemy import Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from trading_ai.database.base import Base

class OpexForecastSnapshotModel(Base):
    __tablename__='opex_forecast_snapshots'
    __table_args__=(UniqueConstraint('symbol','expiration','forecast_timestamp',name='uq_m71_opex_symbol_exp_ts'),)
    forecast_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    symbol:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    expiration:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    cycle_type:Mapped[str]=mapped_column(String(24),nullable=False,index=True)
    dte:Mapped[int]=mapped_column(Integer,nullable=False)
    forecast_timestamp:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    source_as_of_date:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    spot:Mapped[float]=mapped_column(Float,nullable=False)
    range50_low:Mapped[float]=mapped_column(Float,nullable=False); range50_high:Mapped[float]=mapped_column(Float,nullable=False)
    range68_low:Mapped[float]=mapped_column(Float,nullable=False); range68_high:Mapped[float]=mapped_column(Float,nullable=False)
    range90_low:Mapped[float]=mapped_column(Float,nullable=False); range90_high:Mapped[float]=mapped_column(Float,nullable=False)
    magnet:Mapped[float|None]=mapped_column(Float); magnet_probability:Mapped[float]=mapped_column(Float,nullable=False)
    support:Mapped[float|None]=mapped_column(Float); resistance:Mapped[float|None]=mapped_column(Float)
    gamma_flip_current:Mapped[float|None]=mapped_column(Float); gamma_flip_forecast:Mapped[float|None]=mapped_column(Float)
    call_wall_current:Mapped[float|None]=mapped_column(Float); call_wall_forecast:Mapped[float|None]=mapped_column(Float)
    put_wall_current:Mapped[float|None]=mapped_column(Float); put_wall_forecast:Mapped[float|None]=mapped_column(Float)
    dealer_pressure:Mapped[float]=mapped_column(Float,nullable=False)
    confidence:Mapped[float]=mapped_column(Float,nullable=False)
    input_fingerprint:Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class OpexForecastPublicationModel(Base):
    __tablename__='opex_forecast_publications'
    publication_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    publication_name:Mapped[str]=mapped_column(String(96),nullable=False,unique=True,index=True)
    status:Mapped[str]=mapped_column(String(24),nullable=False,index=True)
    published_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    forecast_count:Mapped[int]=mapped_column(Integer,nullable=False)
    authority_input_fingerprint:Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    coverage_status:Mapped[str]=mapped_column(String(32),nullable=False,default='UNKNOWN',index=True)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class OpexForecastOutcomeModel(Base):
    __tablename__='opex_forecast_outcomes'
    outcome_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    forecast_id:Mapped[str]=mapped_column(String(128),nullable=False,unique=True,index=True)
    symbol:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    expiration:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    settlement_price:Mapped[float]=mapped_column(Float,nullable=False)
    in_50:Mapped[int]=mapped_column(Integer,nullable=False); in_68:Mapped[int]=mapped_column(Integer,nullable=False); in_90:Mapped[int]=mapped_column(Integer,nullable=False)
    magnet_distance_pct:Mapped[float|None]=mapped_column(Float)
    realized_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    settlement_symbol:Mapped[str|None]=mapped_column(String(32),nullable=True,index=True)
    settlement_style:Mapped[str|None]=mapped_column(String(64),nullable=True)
    settlement_source:Mapped[str|None]=mapped_column(String(96),nullable=True,index=True)
    sample_group_key:Mapped[str|None]=mapped_column(String(160),nullable=True,index=True)
    horizon_bucket:Mapped[str|None]=mapped_column(String(16),nullable=True,index=True)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)


class OpexSettlementValueModel(Base):
    __tablename__='opex_settlement_values'
    __table_args__=(UniqueConstraint('underlying_symbol','expiration',name='uq_m714_opex_settlement_cycle'),)
    settlement_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    underlying_symbol:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    expiration:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    settlement_symbol:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    settlement_style:Mapped[str]=mapped_column(String(64),nullable=False)
    settlement_value:Mapped[float]=mapped_column(Float,nullable=False)
    settlement_source:Mapped[str]=mapped_column(String(96),nullable=False,index=True)
    observed_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    lineage_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
