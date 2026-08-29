from pathlib import Path
import subprocess

ROOT=Path(__file__).parents[3]
SCRIPT=ROOT/"scripts/m77_forward_shadow/run_combined_forward_shadow.sh"

def test_combined_script_syntax():
    assert subprocess.run(["/bin/bash","-n",str(SCRIPT)]).returncode==0

def test_retired_lunar_block_removed():
    text=SCRIPT.read_text()
    assert "prospective lunar volatility shadow" not in text
    assert "RETIRED_ASTROLOGY_SHADOW" not in text

def test_all_current_tracks_record_and_update():
    text=SCRIPT.read_text()
    for name in [
        "run_m77_24_1_positive_selection_shadow.py",
        "run_m77_26_2_management_geometry_shadow.py",
        "run_m77_27_1_candidate_quality_management_interaction_shadow.py",
        "run_m77_30_cross_sectional_capital_priority_shadow.py",
        "run_m77_40_capacity_aware_capital_allocation_shadow.py",
    ]:
        assert name in text
    assert text.count("--action record") >= 5
    assert text.count("--action update") >= 5

def test_legacy_forward_shadows_preserved():
    text=SCRIPT.read_text()
    assert "m77_6_shadow/run_daily_shadow_collector.sh" in text
    assert "run_m77_13_forward_shadow.py cycle" in text

def test_research_failures_have_no_production_effect():
    assert "production_effect=NONE" in SCRIPT.read_text()
