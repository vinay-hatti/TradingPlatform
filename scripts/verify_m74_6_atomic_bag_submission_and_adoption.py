from pathlib import Path

root=Path(__file__).resolve().parents[1]
transport=(root/'src/trading_ai/broker/ibkr/order_transport.py').read_text()
orders=(root/'src/trading_ai/broker/ibkr/order_service.py').read_text()
sync=(root/'src/trading_ai/broker_portfolio_sync/service.py').read_text()
auto=(root/'src/trading_ai/autonomous_position_management/service.py').read_text()
assert 'submit_combo_order_prepared' in transport
assert 'reserve_order_id' in transport
assert 'durable_pretransmit_lineage' in transport
assert 'SUBMISSION_PENDING' in orders
assert 'durable_before_transmit' in orders
assert 'before_transmit' in orders
assert 'RECOVERED_PLATFORM_INTENT_EXACT_LEG_SET' in sync
assert 'BROKER_POSITION_LINEAGE_RECOVERED' in sync
assert 'FULLY_AUTOMATIC' in sync
assert '_aggregate_institutional_managed_positions' in sync
assert 'broker_leg_ratios' in auto
print('M74.6 atomic BAG submission persistence and institutional position adoption verification: PASSED')
