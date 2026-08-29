from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_valuation_coherent_inputs_are_bulk_preloaded():
    market_inputs = (ROOT / "src/trading_ai/option_valuation_intelligence/market_inputs.py").read_text()
    service = (ROOT / "src/trading_ai/option_valuation_intelligence/service.py").read_text()
    assert "def preload_coherent_market_inputs" in market_inputs
    assert "resolve_coherent_market_inputs(" in market_inputs
    assert "coherent_by_contract, coherent_errors, coherent_preload_profile = preload_coherent_market_inputs" in service
    assert "coherent = load_coherent_market_inputs(" not in service
    assert "coherent_market_preload_seconds" in service


def test_valuation_bulk_preload_keeps_pure_compute_and_single_writer():
    source = (ROOT / "src/trading_ai/option_valuation_intelligence/service.py").read_text()
    block = source[source.index("def _evaluate_job"):source.index("compute_seconds =", source.index("def _evaluate_job"))]
    assert "InstitutionalOptionValuationEngine().evaluate" in block
    assert "s.execute(" not in block
    assert "s.add(" not in block
    assert "PARALLEL_PURE_COMPUTE_SINGLE_WRITER" in source


def test_dealer_now_uses_bulk_preload_only_with_pure_compute_and_single_writer():
    refresh = (ROOT / "src/trading_ai/institutional_market_structure/refresh.py").read_text()
    service = (ROOT / "src/trading_ai/institutional_market_structure/service.py").read_text()
    assert "PARALLEL_PURE_COMPUTE_SINGLE_BULK_WRITER" in refresh
    assert "service.compute_preloaded" in refresh
    assert "InstitutionalMarketStructureService.persist_many" in refresh
    assert "def persist_many(" in service
    assert "POSTGRES_COPY_SINGLE_WRITER" in service
    assert "SQLALCHEMY_BULK_FALLBACK" in service
    assert "SYMBOL_FALLBACK_AFTER_COPY_AND_BULK_FAILURE" in service


def test_volatility_history_is_bulk_loaded_not_queried_per_symbol():
    source = (ROOT / "src/trading_ai/market_intelligence/ingestion_orchestrator.py").read_text()
    assert "history_by_symbol" in source
    assert "closes_by_symbol" in source
    assert 'bindparam("symbols", expanding=True)' in source
    loop = source[source.index("for symbol, contracts in grouped.items():", source.index("def build_volatility_snapshots")):source.index("def build_liquidity_snapshots")]
    assert "SELECT atm_iv_30d FROM underlying_volatility_snapshot WHERE underlying_symbol=:s" not in loop
    assert "SELECT close FROM price_history WHERE symbol=:s" not in loop


def test_stage_order_and_governance_are_unchanged():
    source = (ROOT / "scripts/ingestion_split_common.py").read_text()
    contracts = source.index('execute(\n        "contracts"')
    valuation = source.index("refresh_option_valuation_intelligence(", contracts)
    decisions = source.index('execute(\n        "decisions"', valuation)
    assert contracts < valuation < decisions
    assert "coherent_market=" in source
