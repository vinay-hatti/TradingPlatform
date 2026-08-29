from trading_ai.execution_workspace.service import ExecutionWorkspaceService
from trading_ai.execution_intelligence.service import ExecutionIntelligenceService

workspace_required = (
    "create_from_trade_plan",
    "transition",
    "submit",
    "synchronize",
    "reconcile_entry_with_broker_truth",
    "reprice_working",
    "cancel",
    "_audit",
    "dto",
)
missing_workspace = [name for name in workspace_required if not hasattr(ExecutionWorkspaceService, name)]
assert not missing_workspace, f"ExecutionWorkspaceService missing required methods: {missing_workspace}"

intelligence_required = ("preflight", "assess_working")
missing_intelligence = [name for name in intelligence_required if not hasattr(ExecutionIntelligenceService, name)]
assert not missing_intelligence, f"ExecutionIntelligenceService missing required methods: {missing_intelligence}"

print("M73 execution-workspace integrity verifier: PASS")
print("ExecutionWorkspaceService methods:", ", ".join(workspace_required))
print("ExecutionIntelligenceService methods:", ", ".join(intelligence_required))
