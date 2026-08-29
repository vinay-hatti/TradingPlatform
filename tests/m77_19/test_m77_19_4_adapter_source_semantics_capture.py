from pathlib import Path
import ast, json, py_compile

R = Path("scripts/run_m77_19_4_adapter_source_semantics_capture.py")
C = Path("config/m77/m77_19_4_adapter_source_semantics_capture.json")

def test_compile():
    py_compile.compile(str(R), doraise=True)

def test_capture_is_read_only_to_project_sources():
    x = json.loads(C.read_text())["capture_policy"]
    assert x["production_source_mutation"] is False
    assert x["database_writes"] is False
    assert x["automatic_replay_execution"] is False
    assert x["production_authority_effect"] is False

def test_capture_uses_copy_not_source_rewrite():
    tree = ast.parse(R.read_text())
    calls = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            calls.append(n.func.attr)
    assert "copy2" in calls

def test_primary_sources_frozen():
    x = json.loads(C.read_text())["required_primary_sources"]
    assert "scripts/run_m77_8_daily_pit_replay_authority.py" in x
    assert "scripts/run_m77_9_daily_model_replay.py" in x
    assert "scripts/run_m77_10_monthly_model_replay.py" in x
    assert "scripts/run_m77_2_multiyear_frozen_champion.py" in x
