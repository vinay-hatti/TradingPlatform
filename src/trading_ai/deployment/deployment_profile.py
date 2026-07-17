from dataclasses import dataclass
@dataclass(frozen=True)
class EnvironmentProfile:
 name:str; environment_type:str; deployment_url:str; health_endpoint:str; rollback_endpoint:str
 monitoring_endpoints:tuple[str,...]=(); approval_chain:tuple[str,...]=(); maintenance_window:str=''; policy_reference:str='default'; active:bool=True
 def validate(self):
  for field in ('name','environment_type','deployment_url','health_endpoint','rollback_endpoint'):
   if not getattr(self,field):raise ValueError(f'{field} is required')
class EnvironmentProfileRegistry:
 PROMOTION_ORDER=('DEVELOPMENT','INTEGRATION','QA','UAT','PAPER','STAGING','PRODUCTION')
 def __init__(self,profiles=()):self._profiles={};[self.register(x) for x in profiles]
 def register(self,p):p.validate();self._profiles[p.name.upper()]=p
 def get(self,name):return self._profiles[name.upper()]
 def all(self):return tuple(self._profiles.values())
 def next_environment(self,current):
  i=self.PROMOTION_ORDER.index(current.upper());return None if i+1>=len(self.PROMOTION_ORDER) else self.PROMOTION_ORDER[i+1]
