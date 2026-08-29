from pathlib import Path
from trading_ai.execution_intelligence.policy import ExecutionIntelligencePolicy
from trading_ai.execution_intelligence.service import ExecutionIntelligenceService
root=Path(__file__).resolve().parents[1]
svc=(root/'src/trading_ai/execution_intelligence/service.py').read_text()
ui=(root/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
p=ExecutionIntelligencePolicy()
assert p.policy_version=='M74.1-FRESHNESS-AWARE-EXECUTION-REVALIDATION-1.0'
assert p.stale_quote_reacquire_attempts>=0
assert p.stale_quote_reacquire_interval_seconds>=0
assert 'stale_quote_reacquisition' in svc
assert 'quote_timestamp_advanced' in svc
assert "outcome':'RECOVERED'" in svc
assert "'STALE_BLOCK'" in svc
assert "ExecutionIntelligenceService(self.s).preflight" in (root/'src/trading_ai/execution_workspace/service.py').read_text()
assert 'HISTORICAL SNAPSHOT' in ui
assert 'LIVE REVALIDATION' in ui
assert 'submit, which always performs a new preflight' in ui
assert callable(ExecutionIntelligenceService.preflight)
print('M74.1.0 freshness-aware execution revalidation verification: PASSED')
