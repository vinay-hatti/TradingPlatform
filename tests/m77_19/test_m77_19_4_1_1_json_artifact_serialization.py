from pathlib import Path
import json
import py_compile

R = Path("scripts/run_m77_19_4_1_isolated_adapter_leakage_certification.py")

def test_compile():
    py_compile.compile(str(R), doraise=True)

def test_json_writer_uses_real_newline_not_literal_backslash_n():
    x = R.read_text()
    assert 'tmp.write_text(json.dumps(out,indent=2)+"\\\\n")' not in x
    assert 'tmp.write_text(json.dumps(out,indent=2)+"\\n")' in x

def test_json_writer_validates_before_replace():
    x = R.read_text()
    assert "json.loads(tmp.read_text())" in x
    assert "tmp.replace(OUT)" in x

def test_standard_json_with_newline_is_single_document(tmp_path):
    p = tmp_path / "artifact.json"
    payload = {"status": "READY", "x": 1}
    p.write_text(json.dumps(payload, indent=2) + "\n")
    raw = p.read_text()
    assert raw.endswith("\n")
    assert not raw.endswith("\\n")
    assert json.loads(raw) == payload
