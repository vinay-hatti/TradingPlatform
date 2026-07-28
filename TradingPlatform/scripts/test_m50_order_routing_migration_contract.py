from pathlib import Path
text=Path('migrations/versions/m50_002_ibkr_paper_order_routing.py').read_text()
for value in ['revision=\'m50_002\'','down_revision=\'m50_001\'','broker_orders','broker_executions','broker_order_controls']: assert value in text
print('Milestone 50 IBKR paper-order routing migration contract assertions passed.')
