from pathlib import Path
import json
import py_compile

RUNNER = Path("scripts/run_m77_19_4_1_isolated_adapter_leakage_certification.py")
TEST = Path("tests/m77_19/test_m77_19_4_1_1_json_artifact_serialization.py")

def test_compile():
    py_compile.compile(str(RUNNER), doraise=True)
    py_compile.compile(str(TEST), doraise=True)

def test_runner_uses_real_newline_and_atomic_validation():
    x = RUNNER.read_text()
    assert 'tmp.write_text(json.dumps(out,indent=2)+"\\n")' in x
    assert 'tmp.write_text(json.dumps(out,indent=2)+"\\\\n")' not in x
    assert "json.loads(tmp.read_text())" in x
    assert "tmp.replace(OUT)" in x

def test_regression_test_itself_uses_real_newline():
    x = TEST.read_text()
    assert 'p.write_text(json.dumps(payload, indent=2) + "\\n")' in x
    assert 'p.write_text(json.dumps(payload, indent=2) + "\\\\n")' not in x

def test_python_json_accepts_real_newline(tmp_path):
    p = tmp_path / "x.json"
    payload = {"ok": True}
    p.write_text(json.dumps(payload) + "\n")
    raw = p.read_text()
    assert raw.endswith("\n")
    assert not raw.endswith("\\n")
    assert json.loads(raw) == payload
