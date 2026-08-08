from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_valuation_service_requires_explicit_current_scope():
    text = (ROOT / 'src/trading_ai/option_valuation_intelligence/service.py').read_text()
    assert 'CURRENT_RUN valuation requires explicit opportunity_ids' in text
    assert 'ContractRecommendationModel.opportunity_id.in_(normalized_ids)' in text
    assert "'scope': normalized_scope" in text


def test_options_finalization_passes_current_opportunity_scope():
    text = (ROOT / 'scripts/ingestion_split_common.py').read_text()
    assert 'opportunity_ids=scoped_opportunity_ids' in text
    assert 'scope="CURRENT_RUN"' in text
    assert 'duration_seconds' in text


def test_safe_production_defaults():
    text = (ROOT / 'scripts/run_market_ingestion.py').read_text()
    assert '"--polygon-requests-per-second", type=float, default=8.0' in text
    assert '"--options-batch-size", type=int, default=10000' in text


def test_historical_rebuild_is_explicit():
    text = (ROOT / 'scripts/run_m69_option_valuation_intelligence.py').read_text()
    assert '--scope' in text
    assert 'Use --scope all only for an intentional historical rebuild.' in text
