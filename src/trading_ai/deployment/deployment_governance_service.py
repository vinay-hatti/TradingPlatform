from dataclasses import asdict
from .deployment_policy import DeploymentPolicy
from .deployment_approval_engine import DeploymentApprovalEngine
from .deployment_audit_service import DeploymentAuditEvent,DeploymentAuditService
from .rollback_policy import RollbackPolicy
class DeploymentGovernanceService:
 def __init__(self,policy=None,rollback_policy=None,audit=None):self.policy=policy or DeploymentPolicy();self.rollback_policy=rollback_policy or RollbackPolicy();self.approvals=DeploymentApprovalEngine(self.policy);self.audit=audit or DeploymentAuditService()
 def validate_release(self,release,environment,emergency=False):
  valid,errors=release.validate();allowed,reason=self.policy.deployment_allowed(environment,emergency=emergency);pe=list(errors)
  if self.policy.require_signed_artifact and not release.artifact_signed:pe.append('SIGNED_ARTIFACT_REQUIRED')
  if self.policy.require_release_tag and not release.release_tag:pe.append('RELEASE_TAG_REQUIRED')
  if self.policy.require_rollback_plan and not release.rollback_supported:pe.append('ROLLBACK_SUPPORT_REQUIRED')
  if not allowed:pe.append(reason)
  return {'compliant':valid and not pe,'release_errors':list(errors),'policy_errors':pe,'environment_decision':reason}
 def validate_rollback_plan(self,plan):
  ok,e=plan.validate(self.rollback_policy);return {'valid':ok,'errors':list(e),'plan':asdict(plan)}
 def audit_decision(self,deployment_id,environment,release_version,operator,status,details):self.audit.record(DeploymentAuditEvent(deployment_id,'GOVERNANCE_DECISION',environment,release_version,operator,status,details))
