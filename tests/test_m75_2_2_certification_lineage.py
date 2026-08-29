from pathlib import Path

from trading_ai.trade_plan_certification import certify_institutional_underlying_plan


def stock_cert(entry_low=122.86, entry_high=124.41):
    from trading_ai.trade_plan_certification.engine import plan_fingerprint
    reference={
        'price':259.20,
        'timestamp':'2026-08-13T18:44:45+00:00',
        'source':'LATEST_UNDERLYING_INGESTION',
        'provider':'POLYGON',
    }
    fp=plan_fingerprint(
        direction='BULLISH',reference_market=reference,
        entry_zone_low=entry_low,entry_zone_high=entry_high,
        structural_stop=112.44,targets=[281.30,294.77,299.86],
    )
    return {
        'certification_id':'TPC-NBIS-TEST',
        'status':'PASS',
        'certification_scope':'STOCK_TRADE_PLAN',
        'reference_market':reference,
        'plan_fingerprint':fp,
        'source_plan_fingerprint':fp,
    }


def contract_legs():
    return [
        {'side':'BUY','option_symbol':'O:NBIS260918C00260000','expiry':'2026-09-18','strike':260},
        {'side':'SELL','option_symbol':'O:NBIS260918C00280000','expiry':'2026-09-18','strike':280},
    ]


def management(entry_low,entry_high):
    return {
        'underlying_entry_zone_low':entry_low,
        'underlying_entry_zone_high':entry_high,
        'underlying_stop':112.44,
        'underlying_targets':[281.30,294.77,299.86],
        'trailing_policy':'UNDERLYING_HIGHER_LOW',
        'emergency_option_stop_pct':0.55,
        'theta_exit_days_to_expiry':5,
        'volatility_exit_rule':'EXIT_OR_REDUCE_ON_IV_COLLAPSE_WITH_THESIS_DETERIORATION',
        'assignment_risk_rule':'EXIT_OR_ROLL_SHORT_LEGS_BEFORE_ASSIGNMENT_RISK_WINDOW',
        'management_mode':'PLATFORM_MANAGED_AFTER_FILL',
    }


def test_downstream_mutation_is_bound_and_recertified():
    cert=certify_institutional_underlying_plan(
        stock_certification=stock_cert(),direction='BULLISH',
        entry_zone_low=118.68,entry_zone_high=120.23,structural_stop=112.44,
        targets=[281.30,294.77,299.86],strategy='BULL_CALL_SPREAD',
        legs=contract_legs(),contract_executable=True,dynamic_management=management(118.68,120.23),
    )
    assert cert['status']=='PASS'
    assert cert['certification_scope']=='INSTITUTIONAL_OPTIONS_FINAL_PLAN'
    assert cert['plan_mutated'] is True
    assert cert['lineage_status']=='MUTATED_RECERTIFIED'
    assert cert['source_plan_fingerprint'] != cert['underlying_plan_fingerprint']
    assert cert['trade_builder_ready'] is True


def test_invalid_final_targets_block_trade_builder_readiness():
    cert=certify_institutional_underlying_plan(
        stock_certification=stock_cert(),direction='BULLISH',
        entry_zone_low=118.68,entry_zone_high=120.23,structural_stop=112.44,
        targets=[250.00,294.77,299.86],strategy='BULL_CALL_SPREAD',
        legs=contract_legs(),contract_executable=True,dynamic_management=management(118.68,120.23)|{'underlying_targets':[250.00,294.77,299.86]},
    )
    assert cert['status']=='FAIL'
    assert cert['trade_builder_ready'] is False
    assert 'TPC-GEO-001' in cert['failure_codes']


def test_pipeline_source_contract_moves_readiness_after_final_certification():
    root=Path(__file__).resolve().parents[1]
    valuation=(root/'src/trading_ai/institutional_options/valuation.py').read_text()
    management_src=(root/'src/trading_ai/institutional_options/management.py').read_text()
    handoff=(root/'src/trading_ai/institutional_options/handoff.py').read_text()
    ingestion=(root/'src/trading_ai/institutional_options/opportunity_ingestion.py').read_text()
    repository=(root/'src/trading_ai/institutional_options/repository.py').read_text()
    ui=(root/'ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
    assert 'm75_2_2_final_plan_certification_pending' in valuation
    assert 'Final valued strategy selected' not in valuation
    assert 'certify_institutional_underlying_plan' in management_src
    assert 'MUTATED_RECERTIFIED' in (root/'src/trading_ai/trade_plan_certification/engine.py').read_text()
    assert 'Final Institutional Options plan certified for Trade Builder handoff' in management_src
    assert 'invalidate_ready_for_execution' in management_src
    assert 'source_plan_changed' in ingestion
    assert 'reset_for_source_plan_change' in ingestion
    assert 'TPC-LIN-020' in repository
    assert 'INSTITUTIONAL_OPTIONS_FINAL_PLAN' in handoff
    assert 'Trade plan certification lineage' in ui
    assert 'finalCertified' in ui
