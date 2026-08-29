from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
WRAPPER=ROOT/"scripts/m77_forward_shadow/run_combined_forward_shadow.sh"

def s():
    return WRAPPER.read_text()

def test_existing_m77_6_preserved():
    assert "scripts/m77_6_shadow/run_daily_shadow_collector.sh" in s()

def test_m77_13_runs_after_m77_6():
    x=s()
    assert x.index("run_daily_shadow_collector.sh") < x.index("run_m77_13_forward_shadow.py cycle")

def test_production_lock_respected():
    x=s()
    assert "m69_6_market_pipeline.lock" in x
    assert "WAITING_FOR_PRODUCTION_PIPELINE" in x

def test_research_failure_boundary():
    x=s()
    assert "RESEARCH_DEGRADED" in x
    assert "production_effect=NONE" in x

def test_single_orchestrator_lock():
    assert "m77_forward_shadow_orchestrator.lock" in s()
