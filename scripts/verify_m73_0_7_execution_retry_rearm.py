from pathlib import Path
from trading_ai.execution_workspace.service import ExecutionWorkspaceService
from trading_ai.execution_workspace.models import ExecutionIntentModel
from trading_ai.execution_workspace.repository import ExecutionIntentRepository
ROOT=Path(__file__).resolve().parents[1]
checks={
 'version':ExecutionWorkspaceService.VERSION.startswith('M73.0.7-'),
 'retry_method':hasattr(ExecutionWorkspaceService,'retry_terminal'),
 'broker_terminal_gate':hasattr(ExecutionWorkspaceService,'_assert_retry_broker_terminal'),
 'position_gate':hasattr(ExecutionWorkspaceService,'_assert_no_existing_position'),
 'attempt_column':hasattr(ExecutionIntentModel,'execution_attempt'),
 'parent_column':hasattr(ExecutionIntentModel,'parent_execution_intent_id'),
 'retry_reason_column':hasattr(ExecutionIntentModel,'retry_reason'),
 'repo_attempts':hasattr(ExecutionIntentRepository,'attempts') and hasattr(ExecutionIntentRepository,'next_attempt'),
 'router_retry':"/intents/{id}/retry" in (ROOT/'src/trading_ai/execution_workspace/router.py').read_text(),
 'migration':(ROOT/'migrations/versions/m73_002_governed_execution_retry_rearm.py').exists(),
 'ui_retry':'Retry with fresh preflight' in (ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text(),
 'ui_terminal_immutable':'terminal and immutable' in (ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text(),
 'api_retry':'retry:(id:string' in (ROOT/'ui/workstation/src/api.ts').read_text(),
}
for k,v in checks.items():print(f'{k}: {"PASS" if v else "FAIL"}')
assert all(checks.values()),checks
print('M73.0.7 Governed Execution Retry & Re-arm verifier: PASS')
