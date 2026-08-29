from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/'ui/workstation/src/StockIntelligenceScannerPage.tsx').read_text()

def test_trade_plan_column_and_filter_are_present():
    assert '<th>Trade plan</th>' in SRC
    assert "headerSelect('trade_plan', TRADE_PLAN_FILTER_VALUES)" in SRC
    for value in (
        'CERTIFIED','NOT_CERTIFIED','NOT_EVALUATED','FAILED_MARKET','FAILED_GEOMETRY',
        'FAILED_STRATEGY','FAILED_RISK','FAILED_EXECUTION','FAILED_MANAGEMENT','FAILED_LIFECYCLE',
    ):
        assert f"'{value}'" in SRC

def test_filter_uses_persisted_certification_projection():
    assert 'record.trade_plan_certification || null' in SRC
    assert 'record.trade_plan_certification_status || certification?.status' in SRC
    assert 'tradePlanMatchesFilter(record' in SRC
    assert "filter.startsWith('FAILED_')" in SRC
    assert "failureCodes" in SRC
    assert "TPC-GEO-" in SRC and "TPC-MGMT-" in SRC and "TPC-EXEC-" in SRC

def test_cell_has_expected_operational_states():
    assert "status: 'CERTIFIED' | 'NOT_CERTIFIED' | 'NOT_EVALUATED'" in SRC
    assert "view.status === 'CERTIFIED' ? 'positive'" in SRC
    assert "view.status === 'NOT_CERTIFIED' ? 'negative'" in SRC
    assert 'candidate-status-pill' in SRC

def test_expanded_row_colspan_matches_new_column_count():
    assert 'colSpan={15}' in SRC
