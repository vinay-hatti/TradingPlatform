from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
router=(root/'src/trading_ai/execution_intelligence/router.py').read_text()
service=(root/'src/trading_ai/execution_intelligence/service.py').read_text()
api=(root/'ui/workstation/src/api.ts').read_text()
page=(root/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
ast.parse(service);ast.parse(router)
assert "'/intents/{intent_id}/preview-preflight'" in router
preview_block=router.split("@router.post('/intents/{intent_id}/preview-preflight'",1)[1].split("@router.post('/intents/{intent_id}/preflight'",1)[0]
assert 'Depends(require_access)' in preview_block
assert 'require_mutation_access' not in preview_block
assert 'preview_preflight' in service and 'persist=False' in service
assert 'if persist:' in service
assert 'previewPreflight:' in api and '/preview-preflight' in api
assert 'executionIntelligenceApi.previewPreflight' in page
assert "executionIntelligenceApi.preflight(selected.execution_intent_id" not in page
print('M74.1.0.2 read-only live preflight verification: PASSED')
