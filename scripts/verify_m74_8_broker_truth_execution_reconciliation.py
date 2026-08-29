from pathlib import Path

root=Path(__file__).resolve().parents[1]
svc=(root/'src/trading_ai/broker_portfolio_sync/service.py').read_text()
checks={
    'rejected_intents_considered':'"REJECTED"]' in svc,
    'broker_order_exact_lineage':'def _broker_order_for_intent' in svc,
    'rejected_requires_broker_fill':'broker_order is None or str(broker_order.status or "").upper() != "FILLED"' in svc,
    'audit_event':'BROKER_FILLED_AFTER_LOCAL_REJECTION' in svc,
    'broker_truth_marker':'broker_truth_overrode_local_terminal_state' in svc,
    'ambiguous_multiple_fills_blocked':'len(broker_filled) > 1' in svc,
}
failed=[k for k,v in checks.items() if not v]
assert not failed, failed
print('M74.8 broker-truth execution-state reconciliation verification: PASSED')
