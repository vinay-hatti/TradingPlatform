import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_2_6_native_mt_and_participation_upstream_divergence_forensics.py"
)

spec = importlib.util.spec_from_file_location("m77_526", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_shas_are_pinned():
    assert m.EXPECTED_524_REPORT_SHA256 == "9147873baa5baa3e19e528d6b47d125450316e3a32dfc595ec6064eb2093eb96"
    assert m.EXPECTED_525_REPORT_SHA256 == "a293b8f87ef56762d60989cda3cc03ad224999a1a6d846af7b64e318c48d4e8a"


def test_parity_tolerance_unchanged():
    assert m.PARITY_TOLERANCE == 1e-9


def test_domain_classification():
    assert m.classify_domain("timeframe_states.1w.confidence") == "MT_WEEKLY"
    assert m.classify_domain("participation.adl") == "PARTICIPATION"
    assert m.classify_domain("structure.support") == "STRUCTURE"


def test_confidence_downstream_filter():
    assert m.is_confidence_derived("confidence")
    assert m.is_confidence_derived("scores.confidence")
    assert m.is_confidence_derived(
        "decision_intelligence.explainability.decision_readiness.components.confidence.score"
    )
    assert not m.is_confidence_derived("timeframe_states.1w.confidence")


def test_mt_formula_detection():
    source = """class X:
 def analyze(self,data_by_timeframe):
  states={}
  total=sum(self.weights.get(k,.1) for k in states)
  signed=sum(self.weights.get(k,.1)*self.signed[v.direction] for k,v in states.items())/total
  return {'confidence':round(sum(x.confidence for x in states.values())/len(states),2)}
"""
    result = m.parse_mt_formula(source)
    assert result["confidence_formula_detected_as_unweighted_mean"]
    assert result["direction_formula_uses_timeframe_weights"]


def test_no_database_dependency():
    text = P.read_text()
    assert "SessionLocal" not in text
    assert "DATABASE_URL" not in text
    assert "create_engine(" not in text


def test_blocked_authority():
    text = P.read_text()
    assert '"controlled_exact_input_parity_certified": False' in text
    assert '"full_23_year_reconstruction_authorized": False' in text
    assert '"production_authority_effect": False' in text
