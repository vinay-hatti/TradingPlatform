from __future__ import annotations
from sqlalchemy import Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from trading_ai.database.base import Base

class FuturesContractModel(Base):
    __tablename__='futures_contract_registry'
    ticker:Mapped[str]=mapped_column(String(32),primary_key=True)
    product_code:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    as_of_date:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    first_trade_date:Mapped[str|None]=mapped_column(String(16))
    last_trade_date:Mapped[str|None]=mapped_column(String(16))
    settlement_date:Mapped[str|None]=mapped_column(String(16))
    days_to_maturity:Mapped[int|None]=mapped_column(Integer)
    trading_venue:Mapped[str|None]=mapped_column(String(16))
    active:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class FuturesBarModel(Base):
    __tablename__='futures_bars'
    __table_args__=(UniqueConstraint('ticker','resolution','window_start_ns',name='uq_m712_futures_bar'),)
    id:Mapped[str]=mapped_column(String(128),primary_key=True)
    product_code:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    ticker:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    resolution:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    window_start_ns:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    session_end_date:Mapped[str|None]=mapped_column(String(16),index=True)
    open:Mapped[float]=mapped_column(Float,nullable=False)
    high:Mapped[float]=mapped_column(Float,nullable=False)
    low:Mapped[float]=mapped_column(Float,nullable=False)
    close:Mapped[float]=mapped_column(Float,nullable=False)
    volume:Mapped[float]=mapped_column(Float,nullable=False,default=0)
    dollar_volume:Mapped[float]=mapped_column(Float,nullable=False,default=0)
    transactions:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    settlement_price:Mapped[float|None]=mapped_column(Float)
    source:Mapped[str]=mapped_column(String(32),nullable=False,default='POLYGON_FUTURES')
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class FuturesIntelligenceSnapshotModel(Base):
    __tablename__='futures_intelligence_snapshots'
    snapshot_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    product_code:Mapped[str]=mapped_column(String(16),nullable=False,index=True)
    ticker:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    snapshot_timestamp:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    last_price:Mapped[float]=mapped_column(Float,nullable=False)
    vwap:Mapped[float|None]=mapped_column(Float)
    overnight_high:Mapped[float|None]=mapped_column(Float)
    overnight_low:Mapped[float|None]=mapped_column(Float)
    rth_high:Mapped[float|None]=mapped_column(Float)
    rth_low:Mapped[float|None]=mapped_column(Float)
    trend_score:Mapped[float]=mapped_column(Float,nullable=False)
    momentum_score:Mapped[float]=mapped_column(Float,nullable=False)
    realized_volatility:Mapped[float]=mapped_column(Float,nullable=False)
    basis_pct:Mapped[float|None]=mapped_column(Float)
    confirmation_score:Mapped[float]=mapped_column(Float,nullable=False)
    state:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
