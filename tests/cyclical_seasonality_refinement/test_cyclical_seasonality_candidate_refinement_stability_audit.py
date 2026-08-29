from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RUN=ROOT/"scripts/run_cyclical_seasonality_candidate_refinement_stability_audit.py"
def s():return RUN.read_text()
def test_fail_closed():
 x=s();assert '"production_authority_effect":False' in x;assert '"automatic_shadow_activation":False' in x;assert '"certification_thresholds_relaxed":False' in x
def test_no_gate_relaxation():
 x=s();assert 'q<=0.10' in x;assert 'coverage>=80%' in x;assert 'N>=100' in x
def test_near_miss_fdr_only():
 x=s();assert "NEAR_CERTIFICATION_FDR_ONLY" in x;assert "q is None or q>.20" in x
def test_hierarchical_diagnostic_only():
 x=s();assert '"certification_effect":False' in x;assert "cannot retroactively certify" in x
def test_no_database_access():
 x=s();assert "SessionLocal" not in x;assert "sqlalchemy" not in x
