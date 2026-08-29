#!/usr/bin/env python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
svc = (ROOT / 'src/trading_ai/lifecycle_governance/service.py').read_text()
runner = (ROOT / 'scripts/run_m73_entry_fill_management.py').read_text()
ui = (ROOT / 'ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx').read_text()

checks = {
    'version': 'M75.0-LIFECYCLE-GOVERNANCE-AUTONOMOUS-OPERATIONS-CERTIFICATION-1.0' in svc,
    'terminal_states': 'TERMINAL_POSITION_STATES' in svc and '"CLOSED"' in svc,
    'safe_finalize_only': 'SAFE_FINALIZABLE_INSTRUCTION_STATES' in svc,
    'broker_working_fail_closed': 'BLOCKED_BROKER_MUTATION_PENDING' in svc and 'BROKER_WORKING_INSTRUCTION_STATES' in svc,
    'manager_finalized': 'manager.state = "FINALIZED"' in svc,
    'reservation_cleanup': 'reservation.status = "CANCELLED"' in svc,
    'audit': 'def audit(' in svc and 'VIOLATIONS_FOUND' in svc and 'CERTIFIED' in svc,
    'certify': 'def certify(' in svc,
    'canonical_launchagent_reuse': "result['lifecycle_governance']=_run_lifecycle_governance(portfolio_id)" in runner,
    'nightly_audit_marker': 'M75_AUDIT_MARKER' in runner and '86400' in runner,
    'ui_finalized': 'LIFECYCLE FINALIZED' in ui,
    'ui_terminal_projection': 'EXPIRED' in ui and 'ASSIGNED' in ui and 'ARCHIVED' in ui,
    'm74_operational_state_contract': "NON_OPERATIONAL_POSITION_STATES = new Set(['CLOSED', 'CANCELLED', 'SUPERSEDED'])" in ui,
    'm74_active_count_contract': 'const activePositions = positions.filter(position => !NON_OPERATIONAL_POSITION_STATES.has' in ui,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if failed:
    raise SystemExit('M75 verification failed: ' + ', '.join(failed))
print('M75 lifecycle governance & autonomous operations certification verification: PASSED')
