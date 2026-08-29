import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_2_5_monthly_component_causal_replay_certification.py"
)

spec = importlib.util.spec_from_file_location("m77_525", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


class Obj:
    def __init__(self, confidence):
        self.confidence = confidence


def test_dict_confidence_get_set():
    state = {"confidence": 10.0}
    assert m.get_confidence(state) == 10.0
    m.set_confidence(state, 11.0)
    assert state["confidence"] == 11.0


def test_object_confidence_get_set():
    state = Obj(20.0)
    assert m.get_confidence(state) == 20.0
    m.set_confidence(state, 21.0)
    assert state.confidence == 21.0


def test_exact_tolerance():
    assert m.exact(0.0)
    assert m.exact(1e-10)
    assert not m.exact(1e-6)


def test_authoritative_deltas_fixed():
    assert m.EXPECTED_WEEKLY_CONFIDENCE_DELTA == 0.5
    assert m.EXPECTED_PROFILE_CONFIDENCE_DELTA == 0.24


def test_parity_tolerance_unchanged():
    assert m.PARITY_TOLERANCE == 1e-9


def test_prior_report_sha_pinned():
    assert (
        m.EXPECTED_524_REPORT_SHA256
        == "9147873baa5baa3e19e528d6b47d125450316e3a32dfc595ec6064eb2093eb96"
    )


def test_no_automatic_23_year_authorization():
    text = P.read_text()
    assert '"full_23_year_reconstruction_authorized": False' in text
    assert '"production_authority_effect": False' in text


def test_all_intervention_arms_present():
    text = P.read_text()
    assert '"BASELINE"' in text
    assert '"WEEKLY_ONLY"' in text
    assert '"AGGREGATE_ONLY"' in text
    assert '"WEEKLY_AND_AGGREGATE"' in text
