from datetime import datetime,timezone
from pathlib import Path
import tempfile
from trading_ai.deployment.deployment_policy import DeploymentPolicy,DeploymentWindow
from trading_ai.deployment.release_contract import ReleaseContract
from trading_ai.deployment.deployment_state_machine import DeploymentRun,DeploymentState
from trading_ai.deployment.deployment_approval_engine import DeploymentApprovalEngine
from trading_ai.deployment.environment_promotion_service import EnvironmentPromotionService
from trading_ai.deployment.rollback_policy import RollbackPlan,RollbackTrigger
from trading_ai.deployment.deployment_audit_service import DeploymentAuditService,DeploymentAuditEvent
from trading_ai.deployment.deployment_governance_service import DeploymentGovernanceService
from trading_ai.deployment.deployment_governance_report import DeploymentGovernanceReportBuilder
def main():
 now=datetime(2026,7,17,12,0,tzinfo=timezone.utc);policy=DeploymentPolicy(deployment_window=DeploymentWindow((0,1,2,3,4,5,6),'00:00','23:59'))
 assert policy.deployment_allowed('PRODUCTION',at=now)[0]
 release=ReleaseContract('release-1.0.0','1.0.0','abc123',now.isoformat(),'a'*64,'artifact.tar.gz','m1','c1',deployment_targets=('DEVELOPMENT','INTEGRATION','QA','UAT','PAPER','STAGING','PRODUCTION'),release_tag='v1.0.0',artifact_signed=True)
 assert release.validate()[0]
 run=DeploymentRun('dep-1',release.release_id,'PRODUCTION').transition(DeploymentState.VALIDATED,operator='tester',reason='validated').transition(DeploymentState.APPROVED,operator='tester',reason='approved')
 try:run.transition(DeploymentState.COMPLETED,operator='tester',reason='invalid');raise AssertionError('invalid transition accepted')
 except ValueError:pass
 approvals=DeploymentApprovalEngine(policy);approvals.approve('dep-1','lead','reviewed');assert not approvals.status('dep-1','PRODUCTION')[0];approvals.approve('dep-1','ops','approved');assert approvals.status('dep-1','PRODUCTION')[0]
 promotion=EnvironmentPromotionService();assert promotion.promote(release,'DEVELOPMENT','INTEGRATION','1.0.0','a'*64,'bot').status=='PROMOTED';assert promotion.promote(release,'DEVELOPMENT','PRODUCTION','1.0.0','a'*64,'bot').status=='BLOCKED'
 plan=RollbackPlan('dep-1',RollbackTrigger.MANUAL,'0.9.0','b'*64,'m0','c0',operator='operator');assert plan.validate()[0]
 decision=DeploymentGovernanceService(policy=policy).validate_release(release,'PRODUCTION');assert decision['compliant']
 with tempfile.TemporaryDirectory() as t:
  audit=DeploymentAuditService(Path(t)/'audit.json');audit.record(DeploymentAuditEvent('dep-1','VALIDATED','PRODUCTION','1.0.0','tester','SUCCESS'));assert len(audit.events('dep-1'))==1
  rp=DeploymentGovernanceReportBuilder().write(Path(t)/'report.html',release=release,approvals=approvals.approvals('dep-1'),transitions=run.transitions,promotions=promotion.history(),rollback_plan=plan,compliance=decision);html=rp.read_text()
  assert 'Production Deployment Governance' in html
  [(_ for _ in ()).throw(AssertionError(h)) if h not in html else None for h in DeploymentGovernanceReportBuilder.SECTIONS]
 print('All production deployment governance, release-contract, approval, promotion, rollback, audit, and reporting assertions passed.')
if __name__=='__main__':main()
