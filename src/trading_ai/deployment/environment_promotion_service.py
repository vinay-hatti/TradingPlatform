from dataclasses import dataclass,field
from datetime import datetime,timezone
from .deployment_profile import EnvironmentProfileRegistry
@dataclass(frozen=True)
class PromotionRecord:
 release_id:str;version:str;source_environment:str;target_environment:str;artifact_checksum:str;operator:str;status:str;reason:str;timestamp:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
class EnvironmentPromotionService:
 def __init__(self,registry=None):self.registry=registry or EnvironmentProfileRegistry();self._h=[]
 def validate(self,release,source_environment,target_environment,source_version,source_checksum):
  e=[];source=source_environment.upper();target=target_environment.upper()
  if self.registry.next_environment(source)!=target:e.append('INVALID_PROMOTION_SEQUENCE')
  if source_version!=release.version:e.append('VERSION_MISMATCH')
  if source_checksum!=release.artifact_checksum:e.append('ARTIFACT_CHECKSUM_MISMATCH')
  if target not in tuple(x.upper() for x in release.deployment_targets):e.append('TARGET_NOT_IN_RELEASE_CONTRACT')
  return not e,tuple(e)
 def promote(self,release,source_environment,target_environment,source_version,source_checksum,operator):
  ok,e=self.validate(release,source_environment,target_environment,source_version,source_checksum);r=PromotionRecord(release.release_id,release.version,source_environment.upper(),target_environment.upper(),release.artifact_checksum,operator,'PROMOTED' if ok else 'BLOCKED','PROMOTION_ALLOWED' if ok else ','.join(e));self._h.append(r);return r
 def history(self):return tuple(self._h)
