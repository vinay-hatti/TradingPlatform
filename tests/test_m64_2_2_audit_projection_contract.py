from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_risk_audit_projects_governed_capital_from_authoritative_publication():
    source = (ROOT / "scripts" / "run_m64_2_risk_expiration_audit.py").read_text()
    assert "current_portfolio_allocation" in source
    assert "authoritative_risk_snapshot_id" in source
    assert "capital.get('open_risk',snap.get('open_risk'))" in source
    assert "capital.get('portfolio_heat_pct',snap.get('portfolio_heat_pct'))" in source
    assert "capital.get('trading_risk_basis')" in source
    assert "capital.get('heat_risk_decomposition')" in source
    assert "capital.get('operational_risk')" in source


def test_governance_audit_and_handoff_require_published_authority():
    audit = (ROOT / "scripts" / "run_m76_2_4_portfolio_governance_audit.py").read_text()
    handoff = (ROOT / "src" / "trading_ai" / "institutional_options" / "handoff.py").read_text()
    router = (ROOT / "src" / "trading_ai" / "institutional_options" / "router.py").read_text()
    for source in (audit, handoff, router):
        assert "current_portfolio_allocation" in source
        assert "source_stock_scanner_run_id" in source
    assert "Authoritative current portfolio allocation is missing" in handoff
    assert "_authoritative_portfolio_decision" in router
