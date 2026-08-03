from trading_ai.advanced_trade_builder.contracts import (
    LegSide, OptionRight, TradeLeg, TradePlan, TradePlanState,
)


def plan(state: TradePlanState, valid: bool = True) -> TradePlan:
    return TradePlan(
        trade_plan_id='TP-1', opportunity_id='OP-1', opportunity_version=1,
        intelligence_id=None, account_id='PAPER-PRIMARY', symbol='VTI',
        direction='CALL', strategy='BULL_CALL_SPREAD', state=state, version=2,
        capital=100000.0, risk_budget_pct=1.0, risk_budget_amount=1000.0,
        estimated_debit=200.0, estimated_credit=100.0, max_loss=100.0,
        max_profit=400.0, reward_risk_ratio=4.0, net_greeks={},
        validation={'valid': valid, 'contract_identity_complete': valid},
        legs=(TradeLeg(LegSide.BUY, 1, OptionRight.CALL, 300.0, '2026-09-18', 2.0,
                       option_symbol='O:VTI260918C00300000'),),
        created_by='test', created_at='now', updated_at='now', notes='',
    )


def test_validated_plan_has_approve_and_cancel_actions():
    payload = plan(TradePlanState.VALIDATED).to_dict()
    assert payload['actionable'] is True
    assert payload['allowed_transitions'] == ['APPROVED', 'CANCELLED']
    assert [x['label'] for x in payload['actions']] == ['Approve', 'Cancel']


def test_invalid_draft_keeps_cancel_and_disables_validate():
    payload = plan(TradePlanState.DRAFT, valid=False).to_dict()
    validate = payload['actions'][0]
    assert validate['target_state'] == 'VALIDATED'
    assert validate['enabled'] is False
    assert payload['allowed_transitions'] == ['CANCELLED']


def test_paper_ready_has_execution_action():
    payload = plan(TradePlanState.PAPER_READY).to_dict()
    assert payload['actions'][0]['action'] == 'CREATE_EXECUTION_INTENT'
    assert payload['actions'][0]['enabled'] is True
