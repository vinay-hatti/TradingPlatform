from dataclasses import dataclass,field,replace
from datetime import datetime,timezone
from enum import Enum
class DeploymentState(str,Enum):
 CREATED='CREATED';VALIDATED='VALIDATED';APPROVED='APPROVED';DEPLOYING='DEPLOYING';DEPLOYED='DEPLOYED';VALIDATING='VALIDATING';COMPLETED='COMPLETED';FAILED='FAILED';ROLLING_BACK='ROLLING_BACK';ROLLED_BACK='ROLLED_BACK'
TRANSITIONS={DeploymentState.CREATED:{DeploymentState.VALIDATED,DeploymentState.FAILED},DeploymentState.VALIDATED:{DeploymentState.APPROVED,DeploymentState.FAILED},DeploymentState.APPROVED:{DeploymentState.DEPLOYING,DeploymentState.FAILED},DeploymentState.DEPLOYING:{DeploymentState.DEPLOYED,DeploymentState.FAILED,DeploymentState.ROLLING_BACK},DeploymentState.DEPLOYED:{DeploymentState.VALIDATING,DeploymentState.ROLLING_BACK,DeploymentState.FAILED},DeploymentState.VALIDATING:{DeploymentState.COMPLETED,DeploymentState.FAILED,DeploymentState.ROLLING_BACK},DeploymentState.FAILED:{DeploymentState.ROLLING_BACK},DeploymentState.ROLLING_BACK:{DeploymentState.ROLLED_BACK,DeploymentState.FAILED},DeploymentState.COMPLETED:set(),DeploymentState.ROLLED_BACK:set()}
@dataclass(frozen=True)
class DeploymentTransition:
 from_state:str;to_state:str;operator:str;reason:str;timestamp:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
@dataclass(frozen=True)
class DeploymentRun:
 deployment_id:str;release_id:str;environment:str;state:DeploymentState=DeploymentState.CREATED;transitions:tuple[DeploymentTransition,...]=()
 def transition(self,to_state,operator,reason):
  if to_state not in TRANSITIONS[self.state]:raise ValueError(f'Invalid deployment transition: {self.state.value} -> {to_state.value}')
  ev=DeploymentTransition(self.state.value,to_state.value,operator,reason);return replace(self,state=to_state,transitions=self.transitions+(ev,))
