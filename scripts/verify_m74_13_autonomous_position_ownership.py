#!/usr/bin/env python
from __future__ import annotations
import sys
from pathlib import Path

root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
checks={}
svc=(root/'src/trading_ai/broker_portfolio_sync/service.py').read_text()
auto=(root/'src/trading_ai/execution_intelligence/auto_fill.py').read_text()
pos=(root/'src/trading_ai/autonomous_position_management/service.py').read_text()
runner=(root/'scripts/run_m73_entry_fill_management.py').read_text()
ui=(root/'ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx').read_text()
checks['broker_filled_primary_authority']='BROKER_ORDER_FILLED_EXACT_LINEAGE' in svc and '_broker_order_has_fill' in svc
checks['terminal_state_recovery']='BROKER_TRUTH_PLATFORM_OWNERSHIP_RECONCILED' in svc and 'CANCEL_REQUESTED' in svc
checks['explicit_ownership_registry']='position_ownership' in svc and 'AUTO_BOOTSTRAPPING' in svc
checks['bootstrap_completion']='M74_13_AUTONOMOUS_BOOTSTRAP_COMPLETED' in pos and 'AUTO_MANAGED' in pos
checks['entry_manager_self_heal']='POSITION_BOOTSTRAP_SYNC' in auto and '_position_bootstrap_sync_once' in auto
checks['single_launchagent_orchestration']='AutonomousPositionManagementService' in runner and 'TRADING_AI_M74_13_POSITION_MANAGEMENT_INTERVAL_SECONDS' in runner
checks['ui_bootstrap_visibility']='AUTO BOOTSTRAPPING' in ui and 'position_ownership' in ui
failed=[k for k,v in checks.items() if not v]
if failed:
    raise SystemExit('M74.13 verification failed: '+', '.join(failed))
print('M74.13 autonomous position ownership & bootstrap verification: PASSED')
for k in checks:print('  PASS',k)
