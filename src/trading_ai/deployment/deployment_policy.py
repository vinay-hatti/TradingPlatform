from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
import re
SEMVER_PATTERN=re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")
@dataclass(frozen=True)
class FreezeWindow:
 name:str; start_utc:str; end_utc:str; environments:tuple[str,...]=('PRODUCTION',)
 def active(self,at=None):
  now=at or datetime.now(timezone.utc); start=datetime.fromisoformat(self.start_utc.replace('Z','+00:00')); end=datetime.fromisoformat(self.end_utc.replace('Z','+00:00')); return start<=now<=end
@dataclass(frozen=True)
class DeploymentWindow:
 weekdays:tuple[int,...]=(0,1,2,3,4); start_time_utc:str='08:00'; end_time_utc:str='22:00'
 def allows(self,at=None):
  now=at or datetime.now(timezone.utc)
  if now.weekday() not in self.weekdays:return False
  return time.fromisoformat(self.start_time_utc)<=now.time().replace(tzinfo=None)<=time.fromisoformat(self.end_time_utc)
@dataclass(frozen=True)
class DeploymentPolicy:
 permitted_environments:tuple[str,...]=('DEVELOPMENT','INTEGRATION','QA','UAT','PAPER','STAGING','PRODUCTION')
 production_approval_count:int=2; non_production_approval_count:int=1; emergency_approval_count:int=1
 require_signed_artifact:bool=True; require_release_tag:bool=True; require_rollback_plan:bool=True; require_post_deployment_validation:bool=True
 deployment_timeout_seconds:float=1800.0; minimum_health_score:float=0.95
 deployment_window:DeploymentWindow=field(default_factory=DeploymentWindow); freeze_windows:tuple[FreezeWindow,...]=()
 def validate(self):
  if not self.permitted_environments: raise ValueError('At least one environment is required')
  if self.production_approval_count<=0 or self.emergency_approval_count<=0: raise ValueError('approval counts must be positive')
  if self.non_production_approval_count<0: raise ValueError('non_production_approval_count cannot be negative')
  if self.deployment_timeout_seconds<=0: raise ValueError('deployment_timeout_seconds must be positive')
  if not 0<=self.minimum_health_score<=1: raise ValueError('minimum_health_score must be between 0 and 1')
 def approvals_required(self,environment,emergency=False):
  if emergency:return self.emergency_approval_count
  return self.production_approval_count if environment.upper()=='PRODUCTION' else self.non_production_approval_count
 def deployment_allowed(self,environment,at=None,emergency=False):
  self.validate(); env=environment.upper()
  if env not in self.permitted_environments:return False,'ENVIRONMENT_NOT_PERMITTED'
  if emergency:return True,'EMERGENCY_OVERRIDE'
  now=at or datetime.now(timezone.utc)
  for fw in self.freeze_windows:
   if env in tuple(x.upper() for x in fw.environments) and fw.active(now):return False,f'FREEZE_WINDOW:{fw.name}'
  if not self.deployment_window.allows(now):return False,'OUTSIDE_DEPLOYMENT_WINDOW'
  return True,'DEPLOYMENT_ALLOWED'
def validate_semantic_version(version):return bool(SEMVER_PATTERN.match(version))
