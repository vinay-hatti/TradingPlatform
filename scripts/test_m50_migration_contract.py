from pathlib import Path

path = Path('migrations/versions/m50_001_ibkr_paper_account_foundation.py')
text = path.read_text()
assert 'revision = "m50_001"' in text
assert 'down_revision = "m49_001"' in text
for table in ('broker_account_bindings','broker_account_snapshots','broker_position_snapshots','broker_reconciliation_runs'):
    assert table in text
print('Milestone 50 IBKR paper foundation migration contract assertions passed.')
