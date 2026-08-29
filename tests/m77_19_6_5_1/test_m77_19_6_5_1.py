import ast
import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_1_native_replay_invocation_contract_recovery.py"
)

spec = importlib.util.spec_from_file_location("m77_19_6_5_1", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_sha_deterministic():
    assert m.sha256_text("abc") == m.sha256_text("abc")


def test_call_name_simple():
    node = ast.parse("foo(a)").body[0].value
    assert m.call_name(node) == "foo"


def test_call_name_attribute():
    node = ast.parse("svc.compute(a)").body[0].value
    assert m.call_name(node) == "svc.compute"


def test_assignment_target():
    node = ast.parse("a = 1").body[0]
    assert m.assignment_target_names(node.targets[0]) == ["a"]


def test_classify_weekly():
    p = Path("scripts/run_m77_19_6_isolated_replay_engine_parity.py")
    assert "WEEKLY" in m.classify_path(p)


def test_classify_daily_monthly():
    p = Path("scripts/run_m77_19_3_isolated_daily_monthly_pit_harness.py")
    assert "DAILY_MONTHLY" in m.classify_path(p)


def test_build_adapter_contract_is_not_execution():
    analyses = [
        {
            "path": "scripts/run_m77_19_3_isolated_daily_monthly_pit_harness.py",
            "roles": ["DAILY_MONTHLY"],
            "sha256": "x",
            "target_call_sites": [
                {
                    "call": "build_adapter_contract",
                    "enclosing_function_source": "def main(): pass",
                }
            ],
        }
    ]
    result = m.native_contract_summary(analyses)
    assert result["DAILY_MONTHLY"]["certified_native_contract_resolved"] is False


def test_weekly_native_call_resolves():
    analyses = [
        {
            "path": "scripts/run_m77_19_6_isolated_replay_engine_parity.py",
            "roles": ["WEEKLY"],
            "sha256": "x",
            "target_call_sites": [
                {
                    "call": "isolated_profile",
                    "enclosing_function_source": "def main(): isolated_profile(...)",
                }
            ],
        }
    ]
    result = m.native_contract_summary(analyses)
    assert result["WEEKLY"]["certified_native_contract_resolved"] is True
