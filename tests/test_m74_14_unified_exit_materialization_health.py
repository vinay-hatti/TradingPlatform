from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from trading_ai.dynamic_position_management.service import DynamicPositionManagementService


def test_legacy_canonical_missing_failure_is_the_only_automatic_rearm_class():
    svc = object.__new__(DynamicPositionManagementService)
    legacy = SimpleNamespace(status='SUBMISSION_FAILED', payload={'submission_error': "KeyError: 'canonical order not found: M62-EXIT-PXI-ABC'"})
    broker = SimpleNamespace(status='SUBMISSION_FAILED', payload={'submission_error': 'RuntimeError: IBKR rejected order 110'})
    armed = SimpleNamespace(status='ARMED', payload={'submission_error': "KeyError: 'canonical order not found: M62-EXIT-PXI-ABC'"})
    assert svc._is_legacy_canonical_missing_failure(legacy) is True
    assert svc._is_legacy_canonical_missing_failure(broker) is False
    assert svc._is_legacy_canonical_missing_failure(armed) is False


def test_all_exit_types_share_self_healing_materialization_and_strategy_contract():
    src = (Path(__file__).resolve().parents[1] / 'src/trading_ai/dynamic_position_management/service.py').read_text()
    assert '_ensure_canonical_exit_order' in src
    assert 'result=service.submit(request)' in src
    assert 'result=self._submit_strategy_combo(service,request)' in src
    assert "'unified_exit_materialization':True" in src
    assert "'exit_method':'SINGLE_LEG'" in src
    assert "'strategy_level_exit':True" in src
    assert "'includes_short_legs':True" in src
    assert "'exit_method':'ATOMIC_BAG'" in src
    assert 'if typ=="SHORT_LEG_DTE"' in src


def test_portfolio_projects_current_rules_and_separates_protection_from_profit_targets():
    src = (Path(__file__).resolve().parents[1] / 'ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx').read_text()
    assert 'currentInstructionProjection' in src
    assert 'CRITICAL_PROTECTION_LABELS' in src
    assert 'PROFIT_TARGET_LABELS' in src
    assert 'CRITICAL PROTECTION ACTIVE' in src
    assert 'PROFIT TARGET ATTENTION' in src
    assert 'Management history' in src
    assert 'Critical protection failures' in src
    assert 'Target issues' in src


def test_legacy_failure_rearm_preserves_audit_and_does_not_submit():
    svc = object.__new__(DynamicPositionManagementService)
    svc._event = lambda *args, **kwargs: None
    position = SimpleNamespace(position_id='POS1')
    instruction = SimpleNamespace(
        status='SUBMISSION_FAILED',
        payload={
            'label': 'TARGET_1',
            'submission_error': "KeyError: 'canonical order not found: M62-EXIT-PXI-ABC'",
            'submission_failed_at': '2026-08-12T20:00:00+00:00',
        },
    )
    count = svc._rearm_legacy_canonical_missing_failures(position, [instruction], 'test')
    assert count == 1
    assert instruction.status == 'ARMED'
    assert 'submission_error' not in instruction.payload
    assert instruction.payload['legacy_submission_error_superseded'].startswith('KeyError:')
    assert instruction.payload['submission_failure_history'][0]['recovery'] == 'REARM_FOR_UNIFIED_EXIT_MATERIALIZATION'
    assert instruction.payload['submission_recovery_state'] == 'REARMED_FOR_UNIFIED_EXIT_MATERIALIZATION'
