from dataclasses import dataclass
from enum import Enum
class RollbackTrigger(str,Enum):
 HEALTH_DEGRADATION='HEALTH_DEGRADATION';DEPLOYMENT_TIMEOUT='DEPLOYMENT_TIMEOUT';MIGRATION_FAILURE='MIGRATION_FAILURE';SMOKE_TEST_FAILURE='SMOKE_TEST_FAILURE';SLO_VIOLATION='SLO_VIOLATION';MANUAL='MANUAL'
@dataclass(frozen=True)
class RollbackPolicy:
 automatic_triggers:tuple[RollbackTrigger,...]=(RollbackTrigger.HEALTH_DEGRADATION,RollbackTrigger.DEPLOYMENT_TIMEOUT,RollbackTrigger.MIGRATION_FAILURE,RollbackTrigger.SMOKE_TEST_FAILURE);require_operator_for_manual:bool=True;require_schema_rollback_validation:bool=True;maximum_rollback_seconds:float=900.0
@dataclass(frozen=True)
class RollbackPlan:
 deployment_id:str;trigger:RollbackTrigger;target_artifact_version:str;target_artifact_checksum:str;schema_rollback_version:str|None;configuration_rollback_version:str|None;invalidate_cache:bool=True;restart_services:bool=True;validation_commands:tuple[str,...]=();operator:str|None=None;notes:str=''
 def validate(self,policy=None):
  p=policy or RollbackPolicy();e=[]
  if not self.target_artifact_version:e.append('TARGET_ARTIFACT_VERSION_REQUIRED')
  if len(self.target_artifact_checksum)!=64:e.append('INVALID_TARGET_CHECKSUM')
  if p.require_schema_rollback_validation and self.schema_rollback_version is None:e.append('SCHEMA_ROLLBACK_VERSION_REQUIRED')
  if self.trigger==RollbackTrigger.MANUAL and p.require_operator_for_manual and not self.operator:e.append('MANUAL_OPERATOR_REQUIRED')
  return not e,tuple(e)
