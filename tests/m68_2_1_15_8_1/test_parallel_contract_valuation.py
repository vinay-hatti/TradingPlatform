from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from trading_ai.option_valuation_intelligence.engine import InstitutionalOptionValuationEngine

ROOT = Path(__file__).resolve().parents[2]


def test_contract_optimization_uses_opportunity_isolated_sessions():
    source = (ROOT / 'src/trading_ai/institutional_options/contract_optimization.py').read_text()
    assert 'ThreadPoolExecutor' in source
    assert 'sessionmaker(bind=bind, expire_on_commit=False)' in source
    assert 'worker_service.optimize(' in source
    assert 'max_workers=1' in source
    assert 'worker_session.commit()' in source
    assert 'PARALLEL_OPPORTUNITY_ISOLATED' in source


def test_contract_parallelism_preserves_sqlite_sequential_fallback():
    source = (ROOT / 'src/trading_ai/institutional_options/contract_optimization.py').read_text()
    assert 'dialect' in source
    assert '!= "sqlite"' in source


def test_valuation_uses_preload_parallel_compute_single_writer():
    source = (ROOT / 'src/trading_ai/option_valuation_intelligence/service.py').read_text()
    assert 'decision_by_key' in source
    assert 'inflection_by_symbol' in source
    assert 'dealer_by_symbol' in source
    assert 'existing_valuation_by_key' in source
    assert "thread_name_prefix='m69-valuation'" in source
    assert 'PARALLEL_PURE_COMPUTE_SINGLE_WRITER' in source
    # Compute workers must call the pure engine rather than mutate the ORM session.
    block = source[source.index('def _evaluate_job'):source.index('compute_seconds =', source.index('def _evaluate_job'))]
    assert 'InstitutionalOptionValuationEngine().evaluate' in block
    assert 's.execute(' not in block
    assert 's.add(' not in block


def test_parallel_valuation_engine_is_bitwise_equivalent_to_sequential():
    kwargs = dict(
        opportunity={
            'direction': 'BULLISH',
            'dealer_score': 72,
            'relative_strength': 75,
            'event_pricing_score': 55,
        },
        contract={
            'bid': 2.8,
            'ask': 3.0,
            'underlying_price': 100,
            'strike': 105,
            'dte': 45,
            'right': 'C',
            'implied_volatility': 0.20,
            'realized_volatility_20d': 0.34,
            'liquidity_score': 90,
        },
        inflection={'inflection_score': 78, 'direction': 'BULLISH'},
        siblings=[{'mid': 3.5}, {'mid': 3.3}],
    )
    sequential = [InstitutionalOptionValuationEngine().evaluate(**kwargs) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        parallel = list(executor.map(lambda _: InstitutionalOptionValuationEngine().evaluate(**kwargs), range(8)))
    assert parallel == sequential
    assert len({row['state_hash'] for row in parallel}) == 1


def test_ingestion_logs_parallel_profile_without_changing_stage_order():
    source = (ROOT / 'scripts/ingestion_split_common.py').read_text()
    assert 'parallel_workers' in source
    assert 'execution_mode' in source
    assert 'Option Valuation parallel profile:' in source
    assert source.index('execute(\n        "contracts"') < source.index('refresh_option_valuation_intelligence(' , source.index('execute(\n        "contracts"'))
    assert source.index('refresh_option_valuation_intelligence(' , source.index('execute(\n        "contracts"')) < source.index('execute(\n        "decisions"')
