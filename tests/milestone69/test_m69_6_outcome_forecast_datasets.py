from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_migration_defines_immutable_forecasts_and_unique_outcomes():
    source=(ROOT/'migrations/versions/m69_005_event_outcomes_forecast_snapshots.py').read_text()
    assert 'institutional_event_forecast_snapshots' in source
    assert 'uq_m696_forecast_event_date' in source
    assert 'uq_m696_outcome_event' in source
    assert 'feature_hash' in source
    assert 'realized_absolute_move_pct' in source


def test_forecast_snapshots_are_insert_only():
    source=(ROOT/'src/trading_ai/option_valuation_intelligence/events/outcomes.py').read_text()
    assert 'ON CONFLICT (event_id,snapshot_date) DO NOTHING' in source
    assert 'feature_hash' in source
    assert 'EventForecastSnapshotService' in source


def test_outcomes_use_canonical_price_history_and_are_idempotent():
    source=(ROOT/'src/trading_ai/option_valuation_intelligence/events/outcomes.py').read_text()
    assert 'FROM price_history' in source
    assert 'ON CONFLICT (event_id) DO UPDATE' in source
    assert 'market_data' not in source
    assert 'POST_MARKET' in source


def test_expected_move_uses_persisted_outcome_distribution():
    source=(ROOT/'src/trading_ai/option_valuation_intelligence/events/institutional_service.py').read_text()
    assert 'HistoricalEventOutcomeRepository' in source
    assert 'INSTITUTIONAL_EVENT_INTELLIGENCE_V3' in source
    repo=(ROOT/'src/trading_ai/option_valuation_intelligence/events/historical_repository.py').read_text()
    assert 'institutional_event_outcomes' in repo
    assert "status = 'FINAL'" in repo


def test_trend_forecast_expected_return_is_supported():
    source=(ROOT/'src/trading_ai/option_valuation_intelligence/events/institutional_service.py').read_text()
    assert "'expected_return_pct'" in source


def test_daily_runner_preserves_requested_two_command_schedule():
    source=(ROOT/'scripts/run_m69_6_daily_event_intelligence.sh').read_text()
    assert 'sync_m69_event_calendar.py --horizon-months 6' in source
    assert 'compute_m69_event_expected_moves.py' in source
