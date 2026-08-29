from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
contract = (ROOT / 'src/trading_ai/institutional_options/contract_optimization.py').read_text()
valuation = (ROOT / 'src/trading_ai/option_valuation_intelligence/service.py').read_text()
ingestion = (ROOT / 'scripts/ingestion_split_common.py').read_text()

checks = {
    'contract opportunity isolation': 'PARALLEL_OPPORTUNITY_ISOLATED' in contract,
    'contract worker owns session': 'sessionmaker(bind=bind, expire_on_commit=False)' in contract and 'worker_session.commit()' in contract,
    'valuation preload': all(x in valuation for x in ('decision_by_key', 'inflection_by_symbol', 'dealer_by_symbol', 'existing_valuation_by_key')),
    'valuation pure compute': 'PARALLEL_PURE_COMPUTE_SINGLE_WRITER' in valuation and "thread_name_prefix='m69-valuation'" in valuation,
    'valuation profile': 'parallel_profile' in valuation and 'Option Valuation parallel profile:' in ingestion,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('M68.2.1.15.8.1 verification FAILED: ' + ', '.join(failed))
print('M68.2.1.15.8.1 source verification PASSED')
for name in checks:
    print(' - ' + name)
