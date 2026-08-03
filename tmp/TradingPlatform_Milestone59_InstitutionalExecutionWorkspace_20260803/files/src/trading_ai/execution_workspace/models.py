from sqlalchemy import JSON, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from trading_ai.database.base import Base

class ExecutionIntentModel(Base):
    __tablename__='execution_intents'
    __table_args__=(UniqueConstraint('trade_plan_id','trade_plan_version',name='uq_m59_execution_intent_trade_plan_version'),)
    execution_intent_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    trade_plan_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    trade_plan_version:Mapped[int]=mapped_column(Integer,nullable=False)
    opportunity_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    portfolio_id:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    account_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    symbol:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    strategy:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    state:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    version:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    max_loss:Mapped[float]=mapped_column(Float,nullable=False)
    legs_json:Mapped[list]=mapped_column(JSON,nullable=False)
    order_request_json:Mapped[dict]=mapped_column(JSON,nullable=False)
    validation_json:Mapped[dict]=mapped_column(JSON,nullable=False)
    broker_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_by:Mapped[str]=mapped_column(String(128),nullable=False)
    created_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    updated_at:Mapped[str]=mapped_column(String(64),nullable=False)
    submitted_at:Mapped[str|None]=mapped_column(String(64))
    terminal_at:Mapped[str|None]=mapped_column(String(64))

class ExecutionIntentAuditModel(Base):
    __tablename__='execution_intent_audit_events'
    __table_args__=(UniqueConstraint('execution_intent_id','execution_intent_version',name='uq_m59_execution_intent_audit_version'),)
    event_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    execution_intent_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    execution_intent_version:Mapped[int]=mapped_column(Integer,nullable=False)
    event_type:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    previous_state:Mapped[str|None]=mapped_column(String(32))
    new_state:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    actor:Mapped[str]=mapped_column(String(128),nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    event_timestamp:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
