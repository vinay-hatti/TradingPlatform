from pathlib import Path

root=Path(__file__).resolve().parents[1]
svc=(root/'src/trading_ai/broker_portfolio_sync/service.py').read_text()
test=(root/'tests/test_m74_6_atomic_bag_submission_and_lineage_recovery.py').read_text()
assert 'M74.6.2: promotion is strategy-level' in svc
assert 'for obj in session.new' in svc
assert '_pending_position(canonical_position_id)' in svc
assert 'Last-chance idempotency guard' in svc
assert 'test_strategy_level_promotion_reuses_pending_canonical_position_with_autoflush_disabled' in test
print('M74.6.2 strategy-level canonical position promotion verification: PASSED')
