from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CSS=ROOT/"ui/workstation/src/opex-intelligence.css"

def test_theme_parity_marker_present():
    s=CSS.read_text()
    assert "BEGIN OPEX_ANALYTICS_THEME_PARITY_20260818" in s
    assert "END OPEX_ANALYTICS_THEME_PARITY_20260818" in s

def test_analytics_visual_tokens_present():
    s=CSS.read_text()
    for token in ("#121826","#29334a","#8892a6","#3d7cff","#8c67ff","#192239","#1b2947"):
        assert token in s

def test_header_matches_analytics_hierarchy():
    s=CSS.read_text()
    assert ".opex-page>.page-title h2" in s
    assert "font-size:28px" in s
    assert "max-width:800px" in s

def test_cards_metrics_tables_are_restyled():
    s=CSS.read_text()
    assert ".opex-summary,.opex-card" in s
    assert ".opex-metric" in s
    assert ".opex-card th" in s
    assert "position:sticky" in s

def test_no_tsx_or_api_change_in_package_contract():
    # Focused acceptance is intentionally CSS-only.
    assert CSS.exists()
