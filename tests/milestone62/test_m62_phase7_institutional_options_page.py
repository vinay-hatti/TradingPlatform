from pathlib import Path


def test_parallel_page_is_registered_without_replacing_existing_scanners():
    app = Path('ui/workstation/src/App.tsx').read_text()
    nav = Path('ui/workstation/src/pages.tsx').read_text()
    chrome = Path('ui/workstation/src/WorkspaceChrome.tsx').read_text()
    types = Path('ui/workstation/src/types.ts').read_text()
    assert "scanner: DailyScannerPage" in app
    assert "'option-scanner': OptionScannerPage" in app
    assert "'institutional-options': InstitutionalOptionsPage" in app
    assert "['institutional-options', 'Institutional options'" in nav
    assert "'institutional-options'" in chrome
    assert "'institutional-options'" in types


def test_page_contains_required_decision_workspace_sections():
    page = Path('ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
    for text in (
        'Underlying thesis', 'Dynamic underlying plan', 'Ranked strategy implementations',
        'Exact Polygon contract legs', 'Probability decomposition', 'Workflow actions',
        'Advanced lineage and audit', 'Generate strategies', 'Optimize contracts',
        'Value & rank', 'Generate management', 'Open Trade Builder',
    ):
        assert text in page


def test_workspace_api_exposes_complete_persisted_payload():
    router = Path('src/trading_ai/institutional_options/router.py').read_text()
    assert '@router.get("/workspace/opportunities"' in router
    assert '@router.get("/workspace/opportunities/{opportunity_id}"' in router
    for key in ('"thesis"', '"strategies"', '"contracts"', '"valuations"', '"execution_recommendation"', '"management_snapshots"', '"audit"'):
        assert key in router


def test_frontend_api_uses_parallel_institutional_options_root():
    api = Path('ui/workstation/src/api.ts').read_text()
    assert 'INSTITUTIONAL_OPTIONS_ROOT' in api
    assert 'workspaceList' in api
    assert 'generateStrategies' in api
    assert 'optimizeContracts' in api
    assert 'valueStrategies' in api
    assert 'generateManagement' in api
