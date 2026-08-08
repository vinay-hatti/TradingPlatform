from __future__ import annotations

from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_split_ingestion_scripts_exist_and_preserve_original():
    root = _root()
    assert (root / "scripts/run_market_ingestion.py").is_file()
    assert (root / "scripts/ingest_underlying_data.py").is_file()
    assert (root / "scripts/ingest_options_data.py").is_file()
    assert (root / "scripts/ingestion_split_common.py").is_file()


def test_underlying_and_options_use_distinct_domain_locks_and_shared_finalize_lock():
    root = _root()
    underlying = (root / "scripts/ingest_underlying_data.py").read_text()
    options = (root / "scripts/ingest_options_data.py").read_text()
    common = (root / "scripts/ingestion_split_common.py").read_text()

    assert "underlying_ingestion.lock" in underlying
    assert "options_domain_ingestion.lock" in options
    assert "shared_market_finalization.lock" in underlying
    assert "shared_market_finalization.lock" in options
    assert 'scope="underlying"' in underlying
    assert 'scope="options"' in options
    assert "_exclusive_file_lock" in common


def test_native_domain_orchestrators_finalize_shared_state_once_without_core_main():
    root = _root()
    underlying = (root / "scripts/ingest_underlying_data.py").read_text()
    options = (root / "scripts/ingest_options_data.py").read_text()
    common = (root / "scripts/ingestion_split_common.py").read_text()

    # Native split entry points own their domain work directly. They must not
    # invoke the combined run_market_ingestion.main() wrapper first.
    assert "core.main(" not in underlying
    assert "core.main(" not in options

    assert "core._run_underlying_ingestion" in underlying
    assert "_run_options_domain" in options

    # Each entry point performs exactly one governed shared finalization after
    # domain ingestion. The shared function owns trend/overview/intelligence/
    # market publication/stock publication sequencing.
    assert underlying.count("finalize_shared_state(") == 1
    assert options.count("finalize_shared_state(") == 1

    for stage in (
        "core._run_trend_intelligence_pipeline",
        "core._run_market_overview",
        "core._run_market_intelligence",
        "core._publish_scanner_state",
        "core._publish_stock_intelligence",
    ):
        assert stage in common
