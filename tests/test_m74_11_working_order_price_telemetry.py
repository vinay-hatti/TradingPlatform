from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_working_telemetry_exposes_true_frozen_envelope_and_phase():
    src=(ROOT/'src/trading_ai/execution_intelligence/service.py').read_text()
    assert 'def working_telemetry(self,intent_id)' in src
    assert "'approved_reference_price':reference" in src
    assert "'frozen_boundary_type':'MAXIMUM_DEBIT' if reference>=0 else 'MINIMUM_CREDIT'" in src
    assert "'frozen_boundary_price':boundary" in src
    assert "'envelope_consumed_pct':round(progress,4)" in src
    assert "'phase':phase,'phase_reason':phase_reason" in src
    assert "'reprice_count':reprice_count,'maximum_reprices':int(policy.maximum_reprices)" in src


def test_reprice_audit_persists_post_modify_working_order_telemetry():
    src=(ROOT/'src/trading_ai/execution_workspace/service.py').read_text()
    assert "'reprice_number':int(raw.get('m70_reprice_count',0) or 0)+1" in src
    assert 'telemetry=ExecutionIntelligenceService(self.s).working_telemetry(m.execution_intent_id)' in src
    assert "'working_order_telemetry':telemetry" in src
    assert "'last_working_order_telemetry':telemetry" in src


def test_execution_workspace_polls_read_only_telemetry_and_displays_envelope():
    api=(ROOT/'ui/workstation/src/api.ts').read_text()
    ui=(ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
    assert 'working-telemetry' in api
    assert 'setInterval(poll,5000)' in ui
    assert 'Current working limit' in ui
    assert 'Approved reference' in ui
    assert 'Envelope consumed' in ui
    assert 'Room to boundary' in ui
    assert 'Frozen approval boundary reached' in ui
    assert "x.event_type==='WORKING_ORDER_REPRICED'" in ui
