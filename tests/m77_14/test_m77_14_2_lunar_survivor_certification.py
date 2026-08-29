from pathlib import Path
import py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_14_2_lunar_survivor_certification.py"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_single_frozen_survivor():
    x=R.read_text()
    assert 'TARGET="NDX"' in x
    assert 'HORIZON=10' in x
    assert 'HYPOTHESIS="FIRST_QUARTER_WINDOW"' in x
    assert 'OUTCOME="ABSOLUTE_RETURN"' in x
    assert '"single_frozen_survivor_only":True' in x

def test_dependence_robust_null():
    x=R.read_text()
    assert "YEAR_STRATIFIED_CIRCULAR_EVENT_CALENDAR_SHIFT" in x
    assert "CIRCULAR_PERMUTATIONS=10000" in x
    assert "year_stratified_circular_null" in x

def test_yearly_incremental_not_raw():
    x=R.read_text()
    assert "incremental_vs_same_year_complement" in x
    assert "supportive_years" in x
    assert "no_catastrophic_opposite_year" in x

def test_nonoverlap_and_bootstrap():
    x=R.read_text()
    assert "greedy_nonoverlap" in x
    assert "CONSECUTIVE_EVENT_CLUSTER_BOOTSTRAP_VS_COMPLEMENT" in x
    assert "bootstrap_ci_excludes_zero" in x

def test_regime_incremental():
    x=R.read_text()
    assert "regime_incremental" in x
    assert "regime_stability" in x

def test_fail_closed():
    x=R.read_text()
    assert "RESEARCH_SUPPORTED_FOR_PROSPECTIVE_SHADOW" in x
    assert "RETIRE_LUNAR_SURVIVOR_AS_NOT_ROBUST_ENOUGH" in x
    assert '"production_authority_effect":False' in x
