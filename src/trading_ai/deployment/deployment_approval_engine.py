from dataclasses import dataclass,field
from datetime import datetime,timezone
from .deployment_policy import DeploymentPolicy
@dataclass(frozen=True)
class DeploymentApproval:
 deployment_id:str;approver:str;status:str;reason:str;comments:str='';emergency:bool=False;timestamp:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
class DeploymentApprovalEngine:
 def __init__(self,policy=None):self.policy=policy or DeploymentPolicy();self._a={}
 def record(self,a):self._a.setdefault(a.deployment_id,[]).append(a)
 def approve(self,deployment_id,approver,reason,comments='',emergency=False):
  a=DeploymentApproval(deployment_id,approver,'APPROVED',reason,comments,emergency);self.record(a);return a
 def reject(self,deployment_id,approver,reason,comments=''):
  a=DeploymentApproval(deployment_id,approver,'REJECTED',reason,comments);self.record(a);return a
 def approvals(self,deployment_id):return tuple(self._a.get(deployment_id,()))
 def status(self,deployment_id,environment,emergency=False):
  arr=self.approvals(deployment_id)
  if any(x.status=='REJECTED' for x in arr):return False,'REJECTED'
  distinct={x.approver for x in arr if x.status=='APPROVED' and (not emergency or x.emergency)};required=self.policy.approvals_required(environment,emergency)
  return (True,'APPROVED') if len(distinct)>=required else (False,f'PENDING:{len(distinct)}/{required}')
