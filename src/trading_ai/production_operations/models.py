from __future__ import annotations
from sqlalchemy import JSON, Boolean, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from trading_ai.database.base import Base

class OpsServiceModel(Base):
    __tablename__='production_ops_services'
    service_id:Mapped[str]=mapped_column(String(96),primary_key=True)
    name:Mapped[str]=mapped_column(String(160),nullable=False)
    domain:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    status:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    critical:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
    heartbeat_at:Mapped[str|None]=mapped_column(String(64),index=True)
    last_success_at:Mapped[str|None]=mapped_column(String(64),index=True)
    last_failure_at:Mapped[str|None]=mapped_column(String(64))
    next_run_at:Mapped[str|None]=mapped_column(String(64))
    latency_ms:Mapped[float|None]=mapped_column(Float)
    retry_count:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
    dependencies_json:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    updated_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)

class OpsWorkflowRunModel(Base):
    __tablename__='production_ops_workflow_runs'
    run_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    workflow_name:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    mode:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    status:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    started_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    finished_at:Mapped[str|None]=mapped_column(String(64),index=True)
    actor:Mapped[str]=mapped_column(String(128),nullable=False)
    current_stage:Mapped[str|None]=mapped_column(String(128))
    stage_results_json:Mapped[list]=mapped_column(JSON,nullable=False,default=list)
    error:Mapped[str|None]=mapped_column(Text)
    metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class OpsPublicationFreshnessModel(Base):
    __tablename__='production_ops_publication_freshness'
    __table_args__=(UniqueConstraint('publication_name','source_id',name='uq_m66_publication_source'),)
    freshness_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    publication_name:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    source_id:Mapped[str]=mapped_column(String(160),nullable=False,index=True)
    status:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    published_at:Mapped[str|None]=mapped_column(String(64),index=True)
    age_seconds:Mapped[float|None]=mapped_column(Float)
    maximum_age_seconds:Mapped[int]=mapped_column(Integer,nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    lineage_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    evaluated_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)

class OpsReadinessPublicationModel(Base):
    __tablename__='production_ops_readiness_publications'
    publication_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    publication_name:Mapped[str]=mapped_column(String(128),nullable=False,index=True)
    status:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    scanner_ready:Mapped[bool]=mapped_column(Boolean,nullable=False)
    decision_ready:Mapped[bool]=mapped_column(Boolean,nullable=False)
    execution_ready:Mapped[bool]=mapped_column(Boolean,nullable=False)
    management_ready:Mapped[bool]=mapped_column(Boolean,nullable=False)
    portfolio_ready:Mapped[bool]=mapped_column(Boolean,nullable=False)
    learning_ready:Mapped[bool]=mapped_column(Boolean,nullable=False)
    platform_ready:Mapped[bool]=mapped_column(Boolean,nullable=False)
    published_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False)

class OpsAlertModel(Base):
    __tablename__='production_ops_alerts'
    alert_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    fingerprint:Mapped[str]=mapped_column(String(160),nullable=False,index=True)
    severity:Mapped[str]=mapped_column(String(24),nullable=False,index=True)
    status:Mapped[str]=mapped_column(String(24),nullable=False,index=True)
    category:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    title:Mapped[str]=mapped_column(String(256),nullable=False)
    message:Mapped[str]=mapped_column(Text,nullable=False)
    owner:Mapped[str]=mapped_column(String(128),nullable=False)
    recommended_action:Mapped[str]=mapped_column(Text,nullable=False)
    created_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    updated_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    acknowledged_at:Mapped[str|None]=mapped_column(String(64))
    acknowledged_by:Mapped[str|None]=mapped_column(String(128))
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class OpsRecoveryActionModel(Base):
    __tablename__='production_ops_recovery_actions'
    recovery_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    action_type:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    target_type:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    target_id:Mapped[str]=mapped_column(String(160),nullable=False,index=True)
    status:Mapped[str]=mapped_column(String(32),nullable=False,index=True)
    actor:Mapped[str]=mapped_column(String(128),nullable=False)
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    started_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    finished_at:Mapped[str|None]=mapped_column(String(64))
    result_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class OpsLockModel(Base):
    __tablename__='production_ops_locks'
    lock_name:Mapped[str]=mapped_column(String(160),primary_key=True)
    owner_id:Mapped[str]=mapped_column(String(160),nullable=False,index=True)
    acquired_at:Mapped[str]=mapped_column(String(64),nullable=False)
    heartbeat_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    expires_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    metadata_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)

class OpsAuditEventModel(Base):
    __tablename__='production_ops_audit_events'
    event_id:Mapped[str]=mapped_column(String(128),primary_key=True)
    entity_type:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    entity_id:Mapped[str]=mapped_column(String(160),nullable=False,index=True)
    event_type:Mapped[str]=mapped_column(String(96),nullable=False,index=True)
    actor:Mapped[str]=mapped_column(String(128),nullable=False)
    occurred_at:Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    payload_json:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
