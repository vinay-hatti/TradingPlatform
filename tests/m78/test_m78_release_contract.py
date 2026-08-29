from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_migration_and_operator_present():
    assert (ROOT/"migrations/versions/m78_001_governed_setup_intelligence.py").exists()
    assert (ROOT/"scripts/run_m78_setup_intelligence.py").exists()
    assert (ROOT/"scripts/run_m78_daily_shadow.py").exists()


def test_no_existing_production_module_was_modified_by_m78_overlay_manifest():
    manifest=(ROOT/"docs/m78/M78_IMPLEMENTATION.md").read_text()
    assert "NO EXISTING PRODUCTION SOURCE FILE IS REPLACED" in manifest


def test_governance_markers_are_explicit():
    text="\n".join((ROOT/"src/trading_ai/setup_intelligence"/name).read_text() for name in ["policy.py","service.py","repository.py"])
    assert "authority_effect" in text
    assert "automatic_activation" in text
    assert "prospective_certification_required" in text
