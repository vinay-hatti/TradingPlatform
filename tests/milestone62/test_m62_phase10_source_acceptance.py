from pathlib import Path


def test_phase10_api_runner_and_ui_are_wired():
    root=Path(__file__).resolve().parents[2]
    app=(root/'src/trading_ai/production_api/app.py').read_text()
    api=(root/'ui/workstation/src/api.ts').read_text()
    page=(root/'ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx').read_text()
    runner=(root/'scripts/run_m62_dynamic_position_management.py').read_text()
    assert 'dynamic_position_management_router' in app
    assert 'dynamicPositionManagementApi' in api
    assert 'Dynamic Management Control' in page
    assert '--daemon' in runner and '--interval-seconds' in runner


def test_fill_activation_versions_second_audit_event():
    root=Path(__file__).resolve().parents[2]
    service=(root/'src/trading_ai/execution_workspace/service.py').read_text()
    assert "m.version += 1" in service
    assert "DYNAMIC_MANAGEMENT_ACTIVATED" in service
