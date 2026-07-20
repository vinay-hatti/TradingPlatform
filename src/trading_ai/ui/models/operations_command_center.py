from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from trading_ai.ui.models.paper_commands import GovernedActor

class ServiceHealth(BaseModel):
    service_id:str; display_name:str
    status:Literal['HEALTHY','DEGRADED','UNHEALTHY','UNKNOWN']
    heartbeat_at:datetime|None=None; uptime_seconds:float=0; latency_ms:float=0
    version:str='unknown'; dependencies:list[str]=Field(default_factory=list); details:dict=Field(default_factory=dict)
class HealthTopology(BaseModel):
    generated_at:datetime; overall_status:Literal['HEALTHY','DEGRADED','UNHEALTHY','UNKNOWN']
    services:list[ServiceHealth]; edges:list[dict]
class RuntimeControlRequest(BaseModel):
    service_id:str=Field(min_length=1,max_length=120)
    action:Literal['PAUSE','RESUME','DRAIN','RESTART','REFRESH','DISABLE','ENABLE']
    reason:str=Field(min_length=5,max_length=500); confirmation_token:str=Field(min_length=8,max_length=256); actor:GovernedActor
class RuntimeControlRecord(BaseModel):
    request_id:str; service_id:str; action:str; requested_at:datetime; requested_by:str; reason:str
    status:Literal['REQUESTED','APPROVED','EXECUTED','VERIFIED','REJECTED','FAILED']
    approved_by:str|None=None; approved_at:datetime|None=None; executed_at:datetime|None=None; verification_message:str|None=None
class RuntimeApprovalRequest(BaseModel):
    decision:Literal['APPROVE','REJECT']; reason:str=Field(min_length=5,max_length=500)
    confirmation_token:str=Field(min_length=8,max_length=256); actor:GovernedActor
class IncidentRecord(BaseModel):
    incident_id:str; opened_at:datetime; closed_at:datetime|None=None
    severity:Literal['INFO','WARNING','ERROR','CRITICAL']; service_id:str; title:str; description:str
    status:Literal['OPEN','INVESTIGATING','MITIGATED','RESOLVED']='OPEN'; actor_user_id:str|None=None; resolution:str|None=None
class AlertRecord(BaseModel):
    alert_id:str; created_at:datetime; severity:Literal['INFO','WARNING','ERROR','CRITICAL']
    category:Literal['INFRASTRUCTURE','TRADING','MARKET_DATA','STRATEGY','DATABASE','SECURITY','GOVERNANCE']
    service_id:str; message:str; acknowledged:bool=False; acknowledged_by:str|None=None; acknowledged_at:datetime|None=None
class ReleaseRequest(BaseModel):
    release_version:str=Field(min_length=1,max_length=80); git_commit:str=Field(min_length=7,max_length=80)
    migration_version:str='none'; database_revision:str='none'; installer_version:str
    package_sha256:str=Field(min_length=64,max_length=64); rollback_target:str|None=None
    reason:str=Field(min_length=5,max_length=500); actor:GovernedActor
class ReleaseRecord(BaseModel):
    release_id:str; release_version:str; git_commit:str; migration_version:str; database_revision:str
    installer_version:str; package_sha256:str; deployment_time:datetime; rollback_target:str|None=None
    approved_by:str; deployed_by:str; status:Literal['REGISTERED','DEPLOYED','ROLLED_BACK','FAILED']='REGISTERED'
class OperationalLock(BaseModel):
    lock_name:str; owner_user_id:str; acquired_at:datetime; expires_at:datetime|None=None; reason:str
