import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"scripts/run_m77_19_6_5_2_2_native_compare_profile_parity_certification.py"
s=importlib.util.spec_from_file_location("m",P); m=importlib.util.module_from_spec(s); assert s and s.loader; s.loader.exec_module(m)

def test_semantic_hash_deterministic():
    a=m.canonical_semantic_projection("B",1.0,2.0,"X")
    b=m.canonical_semantic_projection("B",1.0,2.0,"X")
    assert m.semantic_hash(a)==m.semantic_hash(b)

def test_semantic_hash_changes():
    a=m.canonical_semantic_projection("B",1.0,2.0,"X")
    b=m.canonical_semantic_projection("B",1.1,2.0,"X")
    assert m.semantic_hash(a)!=m.semantic_hash(b)

def test_tolerance_is_strict():
    assert m.NUMERIC_TOLERANCE == 1e-9
    assert m.REQUIRED_MATCH_PCT == 100.0

def test_pct():
    assert m.pct(2,2)==100.0
    assert m.pct(0,0)==0.0

def test_projection_rounding():
    p=m.canonical_semantic_projection("A",1.0000000000001,2.0,"C")
    assert p["overall_score"]==1.0
