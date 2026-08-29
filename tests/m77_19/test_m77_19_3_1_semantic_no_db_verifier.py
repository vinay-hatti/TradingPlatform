from pathlib import Path
import ast, py_compile

R = Path("scripts/run_m77_19_3_isolated_daily_monthly_pit_harness.py")

def test_compile():
    py_compile.compile(str(R), doraise=True)

def test_audit_strings_do_not_count_as_db_usage():
    x = R.read_text()
    assert '"contains_sessionlocal": "SessionLocal" in text' in x
    assert "harness_has_production_db_semantics" in x

def test_no_actual_database_import_or_sessionlocal_reference():
    tree = ast.parse(R.read_text())
    imports = []
    refs = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith("trading_ai.database"):
                imports.append(mod)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("trading_ai.database"):
                    imports.append(alias.name)
        elif isinstance(node, ast.Name) and node.id == "SessionLocal":
            refs += 1
    assert imports == []
    assert refs == 0
