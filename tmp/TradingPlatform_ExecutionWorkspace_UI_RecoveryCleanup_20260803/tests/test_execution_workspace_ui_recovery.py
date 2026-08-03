from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
app=(root/'ui/workstation/src/App.tsx').read_text()
chrome=(root/'ui/workstation/src/WorkspaceChrome.tsx').read_text()
pages=(root/'ui/workstation/src/pages.tsx').read_text()
api=(root/'ui/workstation/src/api.ts').read_text()
page=(root/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
router=(root/'src/trading_ai/production_api/router.py').read_text()
assert "execution: ExecutionWorkspacePage" in app
assert "value === 'execution'" in app and "#/execution-workspace" in app
assert "{ label: 'Operations', items: ['command'] }" in chrome
assert "['execution', 'Execution', Waypoints]" not in pages
assert "compatibilityList" in api
assert "list(undefined,'PAPER-PRIMARY')" in page
assert "Unable to load OMS queue" in page
assert "canonical_execution_intents" in router
segment=router[router.index('@router.get("/execution"'):router.index('@router.get("/positions"')]
assert 'artifact_response' not in segment
assert 'ExecutionIntentRepository' in segment
print('Execution Workspace UI recovery cleanup assertions passed.')
