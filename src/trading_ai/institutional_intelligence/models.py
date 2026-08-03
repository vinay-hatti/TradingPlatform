from __future__ import annotations
from sqlalchemy import JSON,String,Integer,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from trading_ai.database.base import Base
class IntelligenceSnapshotModel(Base):
    __tablename__='institutional_intelligence_snapshots'
    __table_args__=(UniqueConstraint('opportunity_id','opportunity_version','analytics_version',name='uq_intelligence_opportunity_version'),)
    intelligence_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    opportunity_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    opportunity_version:Mapped[int]=mapped_column(Integer,nullable=False)
    snapshot_id:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    snapshot_timestamp:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    analytics_version:Mapped[str]=mapped_column(String(32),nullable=False)
    generated_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    generated_by:Mapped[str]=mapped_column(String(128),nullable=False)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False)
