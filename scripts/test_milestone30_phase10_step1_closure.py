from pathlib import Path
def main():
 root=Path(__file__).resolve().parents[1];pkg=root/'src/trading_ai/deployment'
 required=('deployment_policy.py','deployment_profile.py','release_contract.py','deployment_state_machine.py','deployment_approval_engine.py','environment_promotion_service.py','rollback_policy.py','deployment_audit_service.py','deployment_governance_report.py','deployment_governance_service.py','deployment_cli.py')
 [(_ for _ in ()).throw(AssertionError(x)) if not (pkg/x).exists() else None for x in required]
 s=(root/'updated_PROJECT_STATUS.md').read_text();assert 'Step 1' in s and 'COMPLETE' in s
 print('All Milestone 30 Phase 10 Step 1 closure assertions passed.')
if __name__=='__main__':main()
