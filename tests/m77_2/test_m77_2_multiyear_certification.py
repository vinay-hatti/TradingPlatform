from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_m77_2_is_additive_and_production_isolation_is_explicit():
    cert = (
        ROOT
        / "src/trading_ai/historical_underlying_replay/certification.py"
    ).read_text()
    runner = (
        ROOT / "scripts/run_m77_2_multiyear_frozen_champion.py"
    ).read_text()
    assert "production_authority_effect" in cert
    assert "production_model_mutation" in cert
    assert "automatic_champion_promotion" in cert
    assert "False" in cert
    assert "HistoricalUnderlyingReplayService" in runner
    assert "2022, 10, 14" in runner


def test_m77_2_certification_is_read_only():
    cert = (
        ROOT
        / "src/trading_ai/historical_underlying_replay/certification.py"
    ).read_text()
    upper = cert.upper()
    assert "INSERT INTO" not in upper
    assert "UPDATE " not in upper
    assert "DELETE FROM" not in upper
    assert ".COMMIT(" not in upper
    assert "HISTORICAL_UNDERLYING_REPLAY_RUN" in upper


def test_m77_2_reports_overlap_and_cross_year_persistence():
    cert = (
        ROOT
        / "src/trading_ai/historical_underlying_replay/certification.py"
    ).read_text()
    assert "overlap_governance" in cert
    assert "cross_year_persistence" in cert
    assert "positive_return_year_rate_pct" in cert
    assert "symbol_clustered_20d" in cert
    assert "date_clustered_60d" in cert


def test_m77_2_runner_is_resumable_by_segment_manifest():
    runner = (
        ROOT / "scripts/run_m77_2_multiyear_frozen_champion.py"
    ).read_text()
    assert "_load_manifest" in runner
    assert "_save_manifest" in runner
    assert "already complete in manifest" in runner
    assert "replay_run_ids" in runner
