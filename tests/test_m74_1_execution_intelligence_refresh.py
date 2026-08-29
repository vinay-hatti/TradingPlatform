from types import SimpleNamespace

from trading_ai.execution_intelligence import service as service_module
from trading_ai.execution_intelligence.policy import ExecutionIntelligencePolicy
from trading_ai.execution_intelligence.service import ExecutionIntelligenceService
from trading_ai.execution_workspace.models import ExecutionIntentModel
from trading_ai.advanced_trade_builder.models import TradePlanModel


class FakeSession:
    def __init__(self, intent, trade_plan):
        self.intent = intent
        self.trade_plan = trade_plan
        self.commits = 0

    def get(self, model, key):
        if model is ExecutionIntentModel:
            return self.intent
        if model is TradePlanModel:
            return self.trade_plan
        return None

    def commit(self):
        self.commits += 1


def snap(snapshot_id, age, fresh, ts):
    return SimpleNamespace(
        execution_snapshot_id=snapshot_id,
        execution_intent_id='XI-FAST',
        execution_intent_version=2,
        trade_plan_id='TP-FAST',
        symbol='FAST',
        strategy='LONG_CALL',
        decision='EXECUTE' if fresh else 'BLOCK',
        execution_confidence=80.0 if fresh else 70.0,
        approved_reference_price=3.4,
        fresh_executable_price=3.3,
        governed_limit_price=3.2,
        adverse_price_drift_pct=-7.35,
        quote_age_seconds=age,
        fresh_max_loss=315.0,
        risk_budget_amount=50000.0,
        validation_json={'valid': fresh, 'checks': {'quote_timestamp_present': True, 'quote_fresh': fresh}},
        quotes_json={'live_legs': [{'quote_timestamp': ts}]},
        envelope_json={},
        policy_json={},
        evidence_json={},
        created_at='2026-08-10T19:41:25+00:00',
    )


def test_preflight_reacquires_stale_polygon_quote_and_returns_fresh_snapshot(monkeypatch):
    intent = SimpleNamespace(state='APPROVED', trade_plan_id='TP-FAST')
    tp = SimpleNamespace()
    session = FakeSession(intent, tp)
    svc = ExecutionIntelligenceService(session, provider=object())
    rows = [
        snap('M70-OLD', 361.74, False, '2026-08-10T19:30:49+00:00'),
        snap('M70-FRESH', 1.73, True, '2026-08-10T19:41:23+00:00'),
    ]
    calls = []

    def fake_evaluate(*args, **kwargs):
        calls.append(1)
        return rows.pop(0)

    monkeypatch.setattr(svc, '_evaluate', fake_evaluate)
    monkeypatch.setattr(
        service_module,
        'load_execution_intelligence_policy',
        lambda: ExecutionIntelligencePolicy(
            stale_quote_reacquire_attempts=3,
            stale_quote_reacquire_interval_seconds=0,
            policy_version='M74.1-FRESHNESS-AWARE-EXECUTION-REVALIDATION-1.0',
        ),
    )

    result = svc.preflight('XI-FAST', 'tester', 'FAST retry')

    assert len(calls) == 2
    assert result['execution_snapshot_id'] == 'M70-FRESH'
    assert result['decision'] == 'EXECUTE'
    assert result['quote_age_seconds'] == 1.73
    reacq = result['evidence_json']['stale_quote_reacquisition']
    assert reacq['triggered'] is True
    assert reacq['outcome'] == 'RECOVERED'
    assert reacq['quote_timestamp_advanced'] is True
    assert reacq['original_quote_age_seconds'] == 361.74
    assert len(reacq['attempts']) == 2
    assert session.commits == 1


def test_preflight_remains_fail_closed_when_reacquisition_never_becomes_fresh(monkeypatch):
    intent = SimpleNamespace(state='APPROVED', trade_plan_id='TP-FAST')
    tp = SimpleNamespace()
    session = FakeSession(intent, tp)
    svc = ExecutionIntelligenceService(session, provider=object())
    rows = [
        snap('M70-1', 361.0, False, '2026-08-10T19:30:49+00:00'),
        snap('M70-2', 366.0, False, '2026-08-10T19:30:49+00:00'),
        snap('M70-3', 371.0, False, '2026-08-10T19:30:49+00:00'),
    ]

    monkeypatch.setattr(svc, '_evaluate', lambda *a, **k: rows.pop(0))
    monkeypatch.setattr(
        service_module,
        'load_execution_intelligence_policy',
        lambda: ExecutionIntelligencePolicy(
            stale_quote_reacquire_attempts=2,
            stale_quote_reacquire_interval_seconds=0,
            policy_version='M74.1-FRESHNESS-AWARE-EXECUTION-REVALIDATION-1.0',
        ),
    )

    result = svc.preflight('XI-FAST')

    assert result['decision'] == 'BLOCK'
    assert result['validation_json']['checks']['quote_fresh'] is False
    assert result['evidence_json']['stale_quote_reacquisition']['outcome'] == 'STALE_BLOCK'
    assert result['evidence_json']['stale_quote_reacquisition']['quote_timestamp_advanced'] is False
