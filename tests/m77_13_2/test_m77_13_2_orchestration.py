from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
W=ROOT/"scripts/m77_forward_shadow/run_combined_forward_shadow.sh"
def s(): return W.read_text()
def test_preserves_existing_m77_6():
    assert "scripts/m77_6_shadow/run_daily_shadow_collector.sh" in s()
def test_adds_m77_13_after_m77_6():
    x=s(); assert x.index("run_daily_shadow_collector.sh") < x.index("run_m77_13_forward_shadow.py cycle")
def test_waits_for_production_lock():
    x=s(); assert "m69_6_market_pipeline.lock" in x; assert "WAITING_FOR_PRODUCTION_PIPELINE" in x
def test_research_failure_does_not_touch_production():
    x=s(); assert "RESEARCH_DEGRADED" in x; assert "production_effect=NONE" in x
def test_idempotent_orchestrator_lock():
    assert "m77_forward_shadow_orchestrator.lock" in s()
