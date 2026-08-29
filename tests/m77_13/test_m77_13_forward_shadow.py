from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/"scripts/run_m77_13_forward_shadow.py"
MIG=ROOT/"migrations/versions/m77_004_multi_cadence_certified_baseline_forward_shadow.py"

def s():return RUN.read_text()

def test_sessionlocal_and_isolation():
    x=s();assert "from trading_ai.database.session import SessionLocal" in x;assert "production_filter_or_ranking_effect" in x

def test_uses_frozen_certifications():
    x=s();assert "m77_9_daily_walk_forward_certification.json" in x;assert "m77_10_monthly_walk_forward_certification.json" in x

def test_monthly_no_backfill():
    x=s()
    assert "is_actual_month_end_session" in x
    assert "source_date==monthly_anchor" not in x
    assert "monthly_capture_armed" in x

def test_neutral_monthly_context_only():
    x=s();assert "directional_only=True" in x;assert "monthly_neutral_context_only" in x

def test_pit_refreshed():
    x=s();assert "refresh_pit()" in x;assert "m77_8_daily_pit_regime_snapshots.json" in x

def test_idempotent_signal_fingerprint():
    x=s();assert "signal_fingerprint" in x;assert "idempotent_duplicates" in x

def test_migration_chain_and_tables():
    x=MIG.read_text();assert 'revision = "m77_004"' in x;assert 'down_revision = "m77_003"' in x
    assert "m77_13_cadence_states" in x and "m77_13_forward_signals" in x and "m77_13_forward_outcomes" in x
