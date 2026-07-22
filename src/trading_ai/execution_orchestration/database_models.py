from sqlalchemy import JSON, Column, Float, String, Text
from trading_ai.database.base import Base
class ExecutionOrderModel(Base):
    __tablename__='execution_orchestration_orders'
    execution_order_id=Column(String(128),primary_key=True); client_order_id=Column(String(128),nullable=False,index=True); portfolio_id=Column(String(64),nullable=False,index=True); symbol=Column(String(32),nullable=False,index=True); strategy=Column(String(64),nullable=False); status=Column(String(32),nullable=False,index=True); risk_status=Column(String(32),nullable=False); approval_status=Column(String(32),nullable=False); capital_limit=Column(Float,nullable=False); broker_order_id=Column(String(128)); payload_json=Column(JSON,nullable=False)
class ExecutionEventModel(Base):
    __tablename__='execution_orchestration_events'
    event_id=Column(String(128),primary_key=True); execution_order_id=Column(String(128),nullable=False,index=True); event_type=Column(String(64),nullable=False,index=True); from_status=Column(String(32),nullable=False); to_status=Column(String(32),nullable=False); occurred_at=Column(String(64),nullable=False); details_json=Column(JSON,nullable=False)
class ExecutionRunModel(Base):
    __tablename__='execution_orchestration_runs'
    run_id=Column(String(128),primary_key=True); status=Column(String(32),nullable=False,index=True); trading_control=Column(String(64),nullable=False); generated_at=Column(String(64),nullable=False); payload_json=Column(JSON,nullable=False); notes=Column(Text)
