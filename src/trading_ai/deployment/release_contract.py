from dataclasses import dataclass,field
from datetime import datetime,timezone
import re
from .deployment_policy import validate_semantic_version
SHA256_PATTERN=re.compile(r'^[a-fA-F0-9]{64}$')
@dataclass(frozen=True)
class ReleaseContract:
 release_id:str;version:str;git_commit:str;build_timestamp:str;artifact_checksum:str;artifact_location:str;migration_version:str;configuration_version:str
 supported_database_versions:tuple[str,...]=();supported_schema_versions:tuple[str,...]=();minimum_platform_version:str|None=None;maximum_platform_version:str|None=None
 release_notes:str='';rollback_supported:bool=True;deployment_targets:tuple[str,...]=();release_tag:str|None=None;artifact_signed:bool=False;metadata:dict[str,str]=field(default_factory=dict)
 def validate(self):
  e=[]
  if not self.release_id:e.append('RELEASE_ID_REQUIRED')
  if not validate_semantic_version(self.version):e.append('INVALID_SEMANTIC_VERSION')
  if not self.git_commit:e.append('GIT_COMMIT_REQUIRED')
  try:datetime.fromisoformat(self.build_timestamp.replace('Z','+00:00'))
  except ValueError:e.append('INVALID_BUILD_TIMESTAMP')
  if not SHA256_PATTERN.match(self.artifact_checksum):e.append('INVALID_ARTIFACT_CHECKSUM')
  if not self.artifact_location:e.append('ARTIFACT_LOCATION_REQUIRED')
  if not self.migration_version:e.append('MIGRATION_VERSION_REQUIRED')
  if not self.configuration_version:e.append('CONFIGURATION_VERSION_REQUIRED')
  if not self.deployment_targets:e.append('DEPLOYMENT_TARGET_REQUIRED')
  return not e,tuple(e)
