from pathlib import Path
import json, py_compile

R = Path("scripts/run_m77_19_3_isolated_daily_monthly_pit_harness.py")
C = Path("config/m77/m77_19_3_isolated_harness_foundation.json")

def test_compile():
    py_compile.compile(str(R), doraise=True)

def test_no_db_import_in_harness():
    import ast
    tree = ast.parse(R.read_text())

    db_imports = []
    sessionlocal_name_refs = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith("trading_ai.database"):
                db_imports.append(mod)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("trading_ai.database"):
                    db_imports.append(alias.name)
        elif isinstance(node, ast.Name) and node.id == "SessionLocal":
            sessionlocal_name_refs += 1

    assert db_imports == []
    assert sessionlocal_name_refs == 0

def test_no_automatic_execution():
    x = json.loads(C.read_text())["harness_contract"]
    assert x["automatic_historical_replay"] is False
    assert x["production_database_writes"] is False
    assert x["production_table_mutation"] is False

def test_all_missing_cadences_in_contract():
    x = json.loads(C.read_text())["harness_contract"]["date_parameterization_required"]
    assert x == ["DAILY", "MONTHLY", "PIT"]

def test_weekly_reuse_only():
    x = json.loads(C.read_text())["harness_contract"]
    assert x["weekly_existing_range_capability_reused"] is True
