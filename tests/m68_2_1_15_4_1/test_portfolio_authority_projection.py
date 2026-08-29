from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_router_exposes_current_portfolio_authority_summary():
    text=(ROOT/'src/trading_ai/institutional_options/router.py').read_text()
    for token in ['portfolio_authority','selected_in_global_optimum','optimizer_status','AWAITING_CURRENT_AUTHORITY']:
        assert token in text

def test_ui_filters_display_state_not_stale_recorded_state():
    text=(ROOT/'ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
    assert "const display=String((x as any).display_state||x.state)" in text
    assert "display===state" in text

def test_ui_surfaces_optimizer_authority_and_rank():
    text=(ROOT/'ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
    assert 'SELECTED_GLOBAL_FEASIBLE' in text
    assert 'NOT_SELECTED_GLOBAL_FEASIBLE' in text
    assert 'Portfolio: {words((item as any).portfolio_authority.optimizer_status)}' in text

def test_ui_orders_selected_then_rank_then_score():
    text=(ROOT/'ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
    assert "selected_in_global_optimum===true?0" in text
    assert "portfolio_authority?.rank" in text

def test_handoff_remains_fail_closed_on_exact_optimizer_selection():
    text=(ROOT/'src/trading_ai/institutional_options/handoff.py').read_text()
    assert 'optimizer_selection.get("optimality_proven") is not True' in text
    assert '!= "SELECTED_GLOBAL_FEASIBLE"' in text
    assert 'Trade Builder handoff' in text
