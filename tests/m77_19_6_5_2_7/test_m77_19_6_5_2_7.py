import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_2_7_native_timeframe_state_and_participation_causal_intervention_replay.py"
)

spec = importlib.util.spec_from_file_location("m77_527", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


class Obj:
    pass


def test_authority_shas_are_pinned():
    assert m.EXPECTED_525_REPORT_SHA256 == "a293b8f87ef56762d60989cda3cc03ad224999a1a6d846af7b64e318c48d4e8a"
    assert m.EXPECTED_526_REPORT_SHA256 == "80a47e00da8951f15dec66c156f312601e6261bdf37430a1da3dae7d83301187"


def test_candidate_sets_are_narrow():
    assert m.WEEKLY_CANDIDATE_PATHS == (
        "timeframe_states.1w.confidence",
        "timeframe_states.1w.evidence.ema50",
    )
    assert set(m.PARTICIPATION_RAW_EVIDENCE_PATHS) == {
        "participation.evidence.adl",
        "participation.evidence.obv_normalized",
        "participation.evidence.up_down_volume_ratio",
    }
    assert len(m.PARTICIPATION_COMPONENT_PATHS) == 7


def test_parity_tolerance_unchanged():
    assert m.PARITY_TOLERANCE == 1e-9


def test_get_set_path_dict():
    obj = {"a": {"b": 1}}
    assert m.get_path(obj, "a.b") == 1
    m.set_path(obj, "a.b", 2)
    assert obj["a"]["b"] == 2


def test_get_set_path_object():
    root = Obj()
    root.a = Obj()
    root.a.b = 1
    assert m.get_path(root, "a.b") == 1
    m.set_path(root, "a.b", 3)
    assert root.a.b == 3


def test_equivalent_numeric_tolerance():
    assert m.equivalent(1.0, 1.0 + 5e-10)
    assert not m.equivalent(1.0, 1.0 + 5e-8)


def test_validate_526_accepts_required_inventory():
    report = {
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "governance": {"parity_tolerance": 1e-9},
        "upstream_path_inventory": {
            "mt_weekly_candidates": [
                {"path": x} for x in m.WEEKLY_CANDIDATE_PATHS
            ],
            "participation_candidates": [
                {"path": x} for x in m.PARTICIPATION_COMPONENT_PATHS
            ],
        },
    }
    m.validate_526(report)


def test_no_write_sql():
    text = P.read_text()
    assert "SET TRANSACTION READ ONLY" in text
    assert "session.commit(" not in text
    assert "INSERT " not in text
    assert "UPDATE " not in text
    assert "DELETE " not in text


def test_arms_include_required_combined_control():
    assert m.ARMS == (
        "BASELINE",
        "WEEKLY_CANDIDATES",
        "PARTICIPATION_EVIDENCE_ONLY",
        "PARTICIPATION_COMPONENT",
        "WEEKLY_AND_PARTICIPATION_COMPONENT",
    )
