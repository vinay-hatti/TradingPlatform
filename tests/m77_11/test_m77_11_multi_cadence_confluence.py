from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/"scripts/run_m77_11_multi_cadence_confluence.py"
R10=ROOT/"scripts/report_m77_10_monthly_walk_forward.py"

def s(): return RUN.read_text()

def test_backward_only_cadence_binding():
    x=s(); assert "bisect.bisect_right" in x; assert "latest_le" in x; assert '"future_leakage_prohibited":True' in x

def test_predefined_conflict_classes():
    x=s(); assert "FULL_BULLISH_CONFLUENCE" in x; assert "DAILY_BEARISH_COUNTERTREND" in x; assert "WEEKLY_BEARISH_OR_NEUTRAL_CONFLICT" in x

def test_incremental_edge_not_simple_agreement_only():
    x=s(); assert "incremental_vs_best_component_pct" in x; assert "best_component_mean_pct" in x

def test_nonoverlap():
    x=s(); assert "def nonoverlap" in x; assert "i-last>=h" in x

def test_governance():
    x=s(); assert '"database_writes":False' in x; assert '"production_authority_effect":False' in x; assert '"automatic_champion_promotion":False' in x

def test_monthly_reporter_includes_regime():
    x=R10.read_text(); assert 'x.get("regime","UNKNOWN")' in x
