import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parents[2]/"scripts/run_m77_19_6_5_2_1_native_output_schema_compare_contract_forensics.py"
s=importlib.util.spec_from_file_location("m",P); m=importlib.util.module_from_spec(s); assert s and s.loader; s.loader.exec_module(m)

def test_sha():
    import tempfile
    from pathlib import Path
    p=Path(tempfile.mkstemp()[1]); p.write_text("abc")
    assert len(m.sha256_file(p))==64

def test_jsonable_mapping():
    assert m.jsonable({"a":1})=={"a":1}

def test_shape_mapping():
    x=m.structural_shape({"a":1})
    assert x["jsonable_keys"]==["a"]

def test_candidate_shapes():
    b={"frozen_output":{"direction":"B","overall_score":1,"confidence":2,"state_hash":"x"},"frozen_profile":{"p":1},"prediction_identity":{"symbol":"A","as_of":"2020-01-01"}}
    rows=m.candidate_stored_rows(b)
    assert [x[0] for x in rows]==["bundle_flattened","frozen_profile","frozen_output"]
