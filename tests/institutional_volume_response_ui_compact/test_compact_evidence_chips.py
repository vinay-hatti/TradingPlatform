from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CSS=ROOT/"ui/workstation/src/volume_response_evidence.css"
UI=ROOT/"ui/workstation/src/StockIntelligenceScannerPage.tsx"

def test_compact_flex_wrap_layout():
    x=CSS.read_text()
    assert "display: flex !important" in x
    assert "flex-flow: row wrap" in x
    assert "gap: 8px 10px" in x

def test_variable_width_chips():
    x=CSS.read_text()
    assert "flex: 0 0 auto" in x
    assert "width: auto" in x
    assert "min-height: 32px" in x
    assert "padding: 6px 11px" in x

def test_no_fixed_four_column_grid():
    x=CSS.read_text()
    assert "repeat(4" not in x
    assert "grid-template-columns" not in x

def test_semantic_chip_rendering_preserved():
    x=UI.read_text()
    assert "volume-response-evidence-chip" in x
    assert "evidenceTone" in x
    assert "volumeReasons.map" in x
