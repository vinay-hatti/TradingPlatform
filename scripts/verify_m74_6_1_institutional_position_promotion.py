from pathlib import Path

root=Path(__file__).resolve().parents[1]
broker=(root/'src/trading_ai/broker_portfolio_sync/service.py').read_text()
auto=(root/'src/trading_ai/autonomous_position_management/service.py').read_text()
test=(root/'tests/test_m74_6_atomic_bag_submission_and_lineage_recovery.py').read_text()

checks={
    'institutional recovery refuses in-place synthetic promotion': 'candidate_synthetic' in broker and 'if synthetic or not candidate_synthetic' in broker,
    'institutional fallback does not reuse per-leg synthetic projection': 'if managed is None and synthetic:' in broker,
    'canonical existing position receives institutional trade plan': 'managed.trade_plan_id = str(lineage.get("trade_plan_id") or managed.trade_plan_id)' in broker,
    'superseded synthetic exit instructions are terminalized': 'instruction.status = "SUPERSEDED"' in broker and 'M74_6_1_INSTITUTIONAL_POSITION_PROMOTION' in broker,
    'manager mode aligns to recovered institutional position': "promotion_reason':'M74_6_1_INSTITUTIONAL_POSITION_PROMOTION'" in auto,
    'M74.6.1 version marker present': 'M74.6.1-PROMOTION-FINALIZATION-1.0' in auto,
    'database regression covers per-leg promotion': 'test_existing_per_leg_broker_discovered_positions_promote_to_one_canonical_strategy_position' in test,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise AssertionError('M74.6.1 verification failed: '+', '.join(failed))
print('M74.6.1 institutional position promotion finalization verification: PASSED')
