
from __future__ import annotations
from sqlalchemy import Float,Integer,JSON,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from trading_ai.database.base import Base

class M73PositionManagerModel(Base):
    __tablename__='m73_position_managers'
    manager_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    position_id:Mapped[str]=mapped_column(String(128),nullable=False,unique=True,index=True)
    portfolio_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    state:Mapped[str]=mapped_column(String(40),nullable=False,index=True)
    automation_mode:Mapped[str]=mapped_column(String(40),nullable=False)
    protection_state:Mapped[str]=mapped_column(String(40),nullable=False)
    heartbeat_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    activated_at:Mapped[str]=mapped_column(String(64),nullable=False)
    recovered_at:Mapped[str|None]=mapped_column(String(64))
    last_decision:Mapped[str|None]=mapped_column(String(40))
    conviction_score:Mapped[float]=mapped_column(Float,nullable=False,default=50.0)
    thesis_integrity:Mapped[float]=mapped_column(Float,nullable=False,default=.5)
    metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class M73ManagementDecisionModel(Base):
    __tablename__='m73_management_decisions'
    decision_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    position_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    manager_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    cycle_timestamp:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    action:Mapped[str]=mapped_column(String(40),nullable=False,index=True)
    confidence:Mapped[float]=mapped_column(Float,nullable=False)
    conviction_score:Mapped[float]=mapped_column(Float,nullable=False)
    thesis_integrity:Mapped[float]=mapped_column(Float,nullable=False)
    current_stop:Mapped[float|None]=mapped_column(Float)
    current_target:Mapped[float|None]=mapped_column(Float)
    evidence_json:Mapped[dict]=mapped_column(JSON,nullable=False)
    explanation:Mapped[str]=mapped_column(Text,nullable=False)

class M73ExitReservationModel(Base):
    __tablename__='m73_exit_reservations'
    reservation_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    position_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    instruction_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    status:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    reserved_quantity:Mapped[int]=mapped_column(Integer,nullable=False)
    created_at:Mapped[str]=mapped_column(String(64),nullable=False)
    updated_at:Mapped[str]=mapped_column(String(64),nullable=False)
    metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class M73ReplayEventModel(Base):
    __tablename__='m73_replay_events'
    event_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    position_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    event_timestamp:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    sequence_no:Mapped[int]=mapped_column(Integer,nullable=False)
    event_type:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False)
    __table_args__=(UniqueConstraint('position_id','sequence_no',name='uq_m73_replay_position_sequence'),)
