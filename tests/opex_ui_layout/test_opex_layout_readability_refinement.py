from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TSX=ROOT/"ui/workstation/src/OpexIntelligencePage.tsx"
CSS=ROOT/"ui/workstation/src/opex-intelligence.css"

def test_governance_is_horizontal_card_grid():
    s=TSX.read_text()
    assert 'opex-authority-grid' in s
    assert s.count('className="opex-authority-field"') >= 6
    assert 'humanDate(data?.published_at)' in s

def test_human_date_formatter_is_present():
    s=TSX.read_text()
    assert "toLocaleString" in s
    assert "timeZoneName:'short'" in s

def test_summary_has_dedicated_full_width_class():
    s=TSX.read_text()
    assert 'className="opex-summary-narrative"' in s
    c=CSS.read_text()
    assert '.opex-summary .opex-summary-narrative' in c
    assert 'max-width:none' in c
    assert 'font-size:16px' in c

def test_cross_opex_has_uniform_semantic_cards():
    s=TSX.read_text()
    assert 'opex-cross-opex-card' in s
    assert 'opex-transition-facts' in s
    assert 'opex-transition-comparisons' in s
    assert 'opex-transition-metrics' in s
    c=CSS.read_text()
    assert 'grid-template-columns:repeat(auto-fit,minmax(245px,1fr))' in c
    assert 'grid-template-columns:repeat(auto-fit,minmax(360px,1fr))' in c

def test_no_api_or_backend_change():
    s=TSX.read_text()
    assert "opexIntelligenceApi.dashboard(symbol)" in s
    assert "opexIntelligenceApi.refresh(3)" in s
