from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import IntelligenceSnapshotModel
class IntelligenceRepository:
    def __init__(self,session:Session):self.session=session
    def latest(self,opportunity_id): return self.session.scalar(select(IntelligenceSnapshotModel).where(IntelligenceSnapshotModel.opportunity_id==opportunity_id).order_by(IntelligenceSnapshotModel.generated_at.desc()).limit(1))
    def list(self,opportunity_id,limit=20): return list(self.session.scalars(select(IntelligenceSnapshotModel).where(IntelligenceSnapshotModel.opportunity_id==opportunity_id).order_by(IntelligenceSnapshotModel.generated_at.desc()).limit(limit)))
    def add(self,m): self.session.add(m);self.session.flush();return m
