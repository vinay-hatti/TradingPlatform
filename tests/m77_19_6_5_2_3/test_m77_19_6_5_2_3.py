import importlib.util, datetime as dt
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"scripts/run_m77_19_6_5_2_3_monthly_context_parity_difference_forensics.py"
s=importlib.util.spec_from_file_location("m",P); m=importlib.util.module_from_spec(s); assert s and s.loader; s.loader.exec_module(m)

def test_exact_requires_every_semantic_field():
    e={"direction_match":True,"primary_category_match":True,"score_abs_error":0.0,"confidence_abs_error":0.0}
    assert m.exact(e)
    e["confidence_abs_error"]=0.24
    assert not m.exact(e)

def test_errors_are_signed_and_absolute():
    iso={"direction":"B","primary_category":"X","overall_score":9.8,"confidence":85.38}
    st={"direction":"B","primary_category":"X","overall_score":10.0,"confidence":85.62}
    e=m.errors(iso,st)
    assert round(e["score_signed_error"],2)==-0.2
    assert round(e["confidence_signed_error"],2)==-0.24
    assert round(e["score_abs_error"],2)==0.2

def test_candidate_sessions_backtracks():
    sessions=[dt.date(2022,10,d) for d in (24,25,26,27,28,31)]
    got=m.candidate_sessions(dt.date(2022,10,31),sessions)
    assert got[0]==dt.date(2022,10,31)
    assert got[1]==dt.date(2022,10,28)

def test_strict_tolerance():
    assert m.NUMERIC_TOLERANCE == 1e-9

def test_backtrack_is_bounded():
    assert m.MAX_SESSION_BACKTRACK == 8
