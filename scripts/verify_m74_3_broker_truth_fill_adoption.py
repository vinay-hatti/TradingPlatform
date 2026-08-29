from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
auto=(ROOT/'src/trading_ai/execution_intelligence/auto_fill.py').read_text()
ws=(ROOT/'src/trading_ai/execution_workspace/service.py').read_text()
apm=(ROOT/'src/trading_ai/autonomous_position_management/service.py').read_text()
assert 'M74.3-BROKER-TRUTH-FILL-ADOPTION' in auto
assert 'fill_adoption_required=True' in auto
assert 'BrokerPortfolioSynchronizationService(SessionLocal).synchronize' in auto
assert "actor='M74_BROKER_TRUTH_FILL_ADOPTION'" in auto
assert "mapped in {'PARTIALLY_FILLED','FILLED'}" in ws
assert "IBKR_BROKER_TRUTH_FILL_ADOPTION" in ws
assert 'management_generation' in ws
assert 'OPEN_BROKER_QUANTITY_WITHOUT_ACTIVE_EXIT_INSTRUCTIONS' in apm
assert "fill_adoption_source'] = \"IBKR_BROKER_TRUTH\"" in apm or 'fill_adoption_source' in apm
print('M74.3 broker-truth fill adoption verification: PASSED')
