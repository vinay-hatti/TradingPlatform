from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from trading_ai.database.base import Base

def utcnow(): return datetime.now(timezone.utc)
def uid(prefix:str): return f"{prefix}-{uuid4().hex.upper()}"

class LiveTradingPolicyModel(Base):
    __tablename__='live_trading_policies'
    policy_id:Mapped[str]=mapped_column(String(64),primary_key=True,default=lambda:uid('M67-POL'))
    portfolio_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    version:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    status:Mapped[str]=mapped_column(String(32),nullable=False,default='DRAFT')
    environment:Mapped[str]=mapped_column(String(16),nullable=False,default='LIVE')
    live_routing_enabled:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    max_trade_loss_pct:Mapped[float]=mapped_column(Float,nullable=False,default=0.5)
    max_daily_loss_pct:Mapped[float]=mapped_column(Float,nullable=False,default=1.0)
    max_portfolio_heat_pct:Mapped[float]=mapped_column(Float,nullable=False,default=10.0)
    max_contracts:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    max_open_orders:Mapped[int]=mapped_column(Integer,nullable=False,default=5)
    allowed_symbols_json:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    allowed_strategies_json:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    allowed_order_types_json:Mapped[list]=mapped_column(JSON,nullable=False,default=lambda:['LMT'])
    metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    __table_args__=(UniqueConstraint('portfolio_id','version',name='uq_m67_policy_version'),)

class LiveTradingApprovalModel(Base):
    __tablename__='live_trading_approvals'
    approval_id:Mapped[str]=mapped_column(String(64),primary_key=True,default=lambda:uid('M67-APR'))
    portfolio_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    policy_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    approval_type:Mapped[str]=mapped_column(String(32),nullable=False,default='LIVE_ACTIVATION')
    status:Mapped[str]=mapped_column(String(32),nullable=False,default='PENDING')
    requested_by:Mapped[str]=mapped_column(String(128),nullable=False)
    approved_by:Mapped[str|None]=mapped_column(String(128))
    reason:Mapped[str]=mapped_column(String(512),nullable=False,default='')
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)

class LiveTradingKillSwitchModel(Base):
    __tablename__='live_trading_kill_switches'
    switch_id:Mapped[str]=mapped_column(String(64),primary_key=True,default=lambda:uid('M67-KS'))
    portfolio_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    scope:Mapped[str]=mapped_column(String(32),nullable=False,default='ACCOUNT')
    scope_value:Mapped[str]=mapped_column(String(128),nullable=False,default='*')
    active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    action:Mapped[str]=mapped_column(String(32),nullable=False,default='BLOCK_NEW_ORDERS')
    reason:Mapped[str]=mapped_column(String(512),nullable=False)
    activated_by:Mapped[str]=mapped_column(String(128),nullable=False)
    activated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    cleared_by:Mapped[str|None]=mapped_column(String(128))
    cleared_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class LiveTradingCertificationRunModel(Base):
    __tablename__='live_trading_certification_runs'
    run_id:Mapped[str]=mapped_column(String(64),primary_key=True,default=lambda:uid('M67-CERT'))
    portfolio_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    policy_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    status:Mapped[str]=mapped_column(String(32),nullable=False,default='PENDING')
    passed_checks:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    failed_checks:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    checks_json:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    evidence_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class LiveTradingAuditEventModel(Base):
    __tablename__='live_trading_audit_events'
    event_id:Mapped[str]=mapped_column(String(64),primary_key=True,default=lambda:uid('M67-AUD'))
    portfolio_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    event_type:Mapped[str]=mapped_column(String(64),nullable=False)
    actor:Mapped[str]=mapped_column(String(128),nullable=False)
    reason:Mapped[str]=mapped_column(String(512),nullable=False,default='')
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,default=utcnow)
