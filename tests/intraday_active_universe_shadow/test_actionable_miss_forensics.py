from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "report_intraday_actionable_miss_forensics.py"
spec = spec_from_file_location("intraday_actionable_miss_forensics", SCRIPT)
mod = module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_frozen_policy_high_score_route():
    q = mod.qualify(70, {})
    assert q.qualifies is True
    assert q.route == "STOCK_INTELLIGENCE_HIGH_SCORE"


def test_frozen_policy_discovery_route_requires_independent_signal():
    payload = {"breakout": {"state": "BREAKOUT_WATCH"}}
    q = mod.qualify(60, payload)
    assert q.qualifies is True
    assert q.route == "STOCK_INTELLIGENCE_DISCOVERY_COMBINATION"


def test_frozen_policy_below_60_requires_two_domains():
    one = {"breakout": {"state": "BREAKOUT_WATCH"}}
    two = {
        "breakout": {"state": "BREAKOUT_WATCH"},
        "institutional_volume": {"signal": "BUYING_ABSORPTION"},
    }
    assert mod.qualify(59.9, one).qualifies is False
    q = mod.qualify(59.9, two)
    assert q.qualifies is True
    assert q.route == "MULTI_DOMAIN_DISCOVERY_COMBINATION"


def test_classification_initial_admission_blind_spot():
    prev = mod.qualify(72, {})
    cur = mod.qualify(71, {})
    cls, knowable, _ = mod.classify_occurrence(prev, cur)
    assert cls == "INITIAL_ADMISSION_BLIND_SPOT"
    assert knowable is True


def test_classification_dynamic_admission_blind_spot():
    prev = mod.qualify(65, {})
    cur = mod.qualify(65, {"breakout": {"state": "BREAKOUT_WATCH"}})
    cls, knowable, _ = mod.classify_occurrence(prev, cur)
    assert cls == "DYNAMIC_ADMISSION_BLIND_SPOT"
    assert knowable is True


def test_classification_legitimate_late_emergence():
    prev = mod.qualify(55, {})
    cur = mod.qualify(58, {"breakout": {"state": "BREAKOUT_WATCH"}})
    cls, knowable, _ = mod.classify_occurrence(prev, cur)
    assert cls == "LEGITIMATE_LATE_EMERGENCE"
    assert knowable is False


def test_missing_historical_evidence_fails_closed():
    cur = mod.qualify(72, {})
    cls, knowable, _ = mod.classify_occurrence(None, cur)
    assert cls == "UNRESOLVED_EVIDENCE"
    assert knowable is None
