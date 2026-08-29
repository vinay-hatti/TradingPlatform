from pathlib import Path
import re,sys
root=Path(sys.argv[1]).resolve()
api=root/'ui/workstation/src/api.ts';types=root/'ui/workstation/src/types.ts';builder=root/'ui/workstation/src/AdvancedTradeBuilderPage.tsx'

# api.ts: inject retry and attempts into existing executionWorkspaceApi without replacing unrelated APIs.
s=api.read_text()
if 'retry:(id:string' not in s:
    needle='audit:(id:string)=>request<ExecutionIntentAudit[]>'
    i=s.find(needle)
    if i<0: raise SystemExit('Unable to locate executionWorkspaceApi audit method for M73.0.7 API patch')
    inject="retry:(id:string,expectedVersion:number,reason:string)=>request<ExecutionIntent>(`${EXECUTION_WORKSPACE_ROOT}/intents/${encodeURIComponent(id)}/retry`,{method:'POST',headers:headers(true),body:JSON.stringify({expected_version:expectedVersion,reason})}),attempts:(tradePlanId:string,tradePlanVersion?:number)=>request<ExecutionIntent[]>(`${EXECUTION_WORKSPACE_ROOT}/trade-plans/${encodeURIComponent(tradePlanId)}/attempts${tradePlanVersion?`?trade_plan_version=${tradePlanVersion}`:''}`,{headers:headers()}),"
    s=s[:i]+inject+s[i:]
api.write_text(s)

# types.ts: additive optional retry lineage fields.
s=types.read_text()
if 'execution_attempt?:number' not in s:
    s=s.replace('trade_plan_version:number;opportunity_id:string;', 'trade_plan_version:number;execution_attempt?:number;parent_execution_intent_id?:string|null;retry_reason?:string|null;retryable?:boolean;opportunity_id:string;',1)
types.write_text(s)

# Advanced Trade Builder: preserve current page/refinements. Backend create() is terminal-aware; only improve label if possible.
s=builder.read_text()
if 'Open / retry execution' not in s and 'Open execution workspace' in s:
    s=s.replace('>Open execution workspace</button>', '>Open / retry execution</button>')
builder.write_text(s)
print('M73.0.7 UI additive patch: PASS')
