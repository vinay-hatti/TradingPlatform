from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CSS=ROOT/"ui/workstation/src/volume_response_evidence.css"
UI=ROOT/"ui/workstation/src/StockIntelligenceScannerPage.tsx"

def test_evidence_grid_present():
    x=UI.read_text()
    assert "volume-response-evidence-grid" in x
    assert "volume-response-evidence-chip" in x

def test_reason_codes_render_individually():
    x=UI.read_text()
    assert "volumeReasons.map" in x
    assert "key={reason}" in x

def test_semantic_tones():
    x=UI.read_text()
    assert "evidenceTone" in x
    assert "DISTRIBUTION" in x
    assert "ACCUMULATION" in x

def test_css_spacing_and_compact_wrap():
    x=CSS.read_text()
    assert "display: flex !important" in x
    assert "flex-flow: row wrap" in x
    assert "gap: 8px 10px" in x
    assert "flex: 0 0 auto" in x
    assert "width: auto" in x
    assert "repeat(4" not in x
    assert "grid-template-columns" not in x
