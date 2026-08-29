from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_scheduled_polygon_capture_restored_to_single_worker():
    for name in ("run_intraday.sh", "run_morning.sh", "run_eod.sh"):
        source = (ROOT / "scripts/m69_6_scheduled" / name).read_text()
        assert "--polygon-network-workers 1" in source
        assert "--polygon-network-workers 4" not in source


def test_polygon_concurrency_capability_is_retained_for_manual_profiling():
    provider = (ROOT / "src/trading_ai/scanner/options_market_data_ingestion/polygon_snapshot_provider.py").read_text()
    parser = (ROOT / "scripts/run_market_ingestion.py").read_text()
    assert "CONCURRENT_SYMBOL_CAPTURE_GLOBAL_RATE_LIMIT" in provider
    assert "self._throttle_lock = threading.Lock()" in provider
    assert '"--polygon-network-workers"' in parser


def test_dealer_uses_pure_parallel_compute_then_single_bulk_writer():
    refresh = (ROOT / "src/trading_ai/institutional_market_structure/refresh.py").read_text()
    service = (ROOT / "src/trading_ai/institutional_market_structure/service.py").read_text()
    assert "PARALLEL_PURE_COMPUTE_SINGLE_BULK_WRITER" in refresh
    assert "service.compute_preloaded" in refresh
    compute_block = refresh[refresh.index("def compute_one"):refresh.index("compute_started =", refresh.index("def compute_one"))]
    assert "persist" not in compute_block
    assert "create_session" not in compute_block
    assert "InstitutionalMarketStructureService.persist_many" in refresh
    assert "def persist_many(" in service
    assert '"POSTGRES_COPY_SINGLE_WRITER"' in service
    assert '"SQLALCHEMY_BULK_FALLBACK"' in service
    assert '"SYMBOL_FALLBACK_AFTER_COPY_AND_BULK_FAILURE"' in service


def test_dealer_bulk_writer_uses_copy_then_batched_sqlalchemy_fallback_and_one_normal_commit():
    source = (ROOT / "src/trading_ai/institutional_market_structure/service.py").read_text()
    block = source[source.index("def persist_many("):source.index("@staticmethod\n    def _persist", source.index("def persist_many("))]
    assert "_postgres_copy_rows" in block
    assert "copy_batch_size" in source
    assert "session.execute(statement, mappings" in block
    assert "session.commit()" in block
    assert "POSTGRES_COPY_SINGLE_WRITER" in block
    assert "SQLALCHEMY_BULK_FALLBACK" in block
    assert "SYMBOL_FALLBACK_AFTER_COPY_AND_BULK_FAILURE" in block


def test_dealer_fail_fast_and_adapter_path_remain_legacy_compatible():
    source = (ROOT / "src/trading_ai/institutional_market_structure/refresh.py").read_text()
    assert "and continue_on_error" in source
    assert "self.service_factory is None" in source
    assert "return self._run_legacy" in source


def test_dealer_runtime_profile_exposes_bulk_writer_substages():
    source = (ROOT / "scripts/run_market_ingestion.py").read_text()
    assert "Dealer timing profile:" in source
    assert "compute_wall=" in source
    assert "bulk_insert_seconds" in source
    assert "bulk_commit_seconds" in source
