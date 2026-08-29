import ast
import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_1_1_imported_native_contract_resolution.py"
)

spec = importlib.util.spec_from_file_location("m", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_dm_required():
    assert m.DM_REQUIRED_FUNCTIONS == ("snapshot", "daily_dates", "monthly_dates")


def test_weekly_required():
    assert m.WEEKLY_REQUIRED_FUNCTIONS == ("isolated_profile", "call_profile", "main")


def test_sha():
    assert m.sha256_text("a") == m.sha256_text("a")


def test_call_name_simple():
    node = ast.parse("call_profile(a)").body[0].value
    assert m.call_name(node) == "call_profile"


def test_calls_named():
    text = "def x():\n    call_profile(a,b)\n"
    tree = ast.parse(text)
    rows = m.calls_named(text, tree, {"call_profile"})
    assert len(rows) == 1


def test_assignments_matching():
    text = "def x():\n    session_set = set(spy_dates)\n"
    tree = ast.parse(text)
    rows = m.assignments_matching(text, tree, ("session_set",))
    assert len(rows) == 1
