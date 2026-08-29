from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/"scripts/run_cyclical_seasonality_frozen_candidate_targeted_robustness.py"

def src(): return RUN.read_text()

def test_frozen_identity_is_exact():
    s=src()
    assert "STATE_PERSISTENCE::category_age_bucket::AGE_2_3::STRONG_BULLISH::20" in s
    assert '"horizon": 20' in s

def test_existing_certification_gate_is_not_relaxed():
    s=src()
    assert '"max_fdr_q_each_full_year": 0.10' in s
    assert '"min_coverage_pct_each_full_year": 80.0' in s
    assert '"min_matched_n_each_full_year": 100' in s
    assert '"min_matched_excess_pct_each_full_year": 0.25' in s

def test_shadow_and_production_are_fail_closed():
    s=src()
    assert '"automatic_shadow_activation":False' in s
    assert '"production_authority_effect":False' in s
    assert '"certification_thresholds_relaxed":False' in s

def test_neighbor_search_is_prohibited():
    s=src()
    assert '"neighbor_candidate_search_prohibited":True' in s
    assert "expected exactly one frozen candidate" in s

def test_observation_robustness_does_not_certify():
    s=src()
    assert '"certification_effect": False' in s
    assert "cannot retroactively certify" in s

def test_artifact_only_no_database_dependency():
    s=src()
    assert "SessionLocal" not in s
    assert "sqlalchemy" not in s
