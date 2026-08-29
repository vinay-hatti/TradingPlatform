from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_migration_attempt_identity():
 s=(ROOT/'migrations/versions/m73_002_governed_execution_retry_rearm.py').read_text();assert 'execution_attempt' in s;assert 'uq_m73_execution_intent_trade_plan_attempt' in s
def test_terminal_retry_guards():
 s=(ROOT/'src/trading_ai/execution_workspace/service.py').read_text();assert "RETRYABLE_TERMINAL_STATES={'REJECTED','CANCELLED','EXPIRED'}" in s;assert "parent.state=='CANCEL_REQUESTED'" in s;assert '_assert_retry_broker_terminal(parent)' in s;assert '_assert_no_existing_position(parent)' in s
def test_retry_creates_new_attempt():
 s=(ROOT/'src/trading_ai/execution_workspace/service.py').read_text();assert 'attempt=self.repo.next_attempt' in s;assert "event='EXECUTION_RETRY_CREATED' if parent" in s;assert "retry_requires_fresh_preflight':True" in s
def test_ui_terminal_retry():
 s=(ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text();assert 'Retry with fresh preflight' in s;assert 'terminal and immutable' in s
def test_router_retry():
 s=(ROOT/'src/trading_ai/execution_workspace/router.py').read_text();assert "@router.post('/intents/{id}/retry'" in s
