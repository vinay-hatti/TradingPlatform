from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]
def test_preview_route_is_read_only_guarded():
    text=(ROOT/'src/trading_ai/execution_intelligence/router.py').read_text();ast.parse(text)
    block=text.split("@router.post('/intents/{intent_id}/preview-preflight'",1)[1].split("@router.post('/intents/{intent_id}/preflight'",1)[0]
    assert 'Depends(require_access)' in block
    assert 'require_mutation_access' not in block

def test_preview_service_does_not_persist():
    text=(ROOT/'src/trading_ai/execution_intelligence/service.py').read_text();ast.parse(text)
    assert "def preview_preflight" in text
    assert "persist=False" in text
    assert "if persist:" in text

def test_workspace_uses_preview_not_mutating_preflight():
    api=(ROOT/'ui/workstation/src/api.ts').read_text()
    page=(ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
    assert 'previewPreflight:' in api and '/preview-preflight' in api
    assert 'executionIntelligenceApi.previewPreflight' in page
