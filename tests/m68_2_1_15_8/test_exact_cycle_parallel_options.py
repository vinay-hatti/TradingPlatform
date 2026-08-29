from __future__ import annotations

import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from trading_ai.institutional_market_structure.refresh import DealerPositionRefreshOrchestrator
from trading_ai.scanner.options_market_data_ingestion.persistence import GovernedOptionSnapshotWriter
from trading_ai.scanner.options_market_data_quality.contracts import OptionContractIdentity, OptionQuoteRecord, OptionSide

ROOT = Path(__file__).resolve().parents[2]


def test_governed_snapshot_writer_maps_exact_validated_record_without_daily_lookup():
    writer = GovernedOptionSnapshotWriter(object(), snapshot_run_id=77, snapshot_timestamp=datetime(2026, 8, 17, 20, 0, tzinfo=timezone.utc))
    record = OptionQuoteRecord(
        identity=OptionContractIdentity("AAPL", date(2026, 9, 18), 220.0, OptionSide.CALL),
        quote_date=date(2026, 8, 17),
        bid=5.0,
        ask=5.4,
        last=5.2,
        volume=100,
        open_interest=250,
        implied_volatility=0.31,
        delta=0.51,
        gamma=0.02,
        theta=-0.08,
        vega=0.14,
        provider_symbol="O:AAPL260918C00220000",
    )
    params = writer._params(record)
    assert params["snapshot_run_id"] == 77
    assert params["option_symbol"] == "O:AAPL260918C00220000"
    assert params["quote_quality"] == "COMPLETE_QUOTE"
    assert params["mark"] == 5.2


def test_ingestion_dual_writes_exact_snapshot_before_manifest_completion():
    source = (ROOT / "src/trading_ai/scanner/options_market_data_ingestion/service.py").read_text()
    assert "GovernedOptionSnapshotWriter" in source
    assert "self.snapshot_writer.write(valid_records)" in source
    assert source.index("self.snapshot_writer.write(valid_records)") < source.index("self.manifest_store.mark_completed")


def test_snapshot_finalization_prunes_earlier_same_day_contracts_and_never_rebuilds_membership_from_quote_date():
    source = (ROOT / "src/trading_ai/market_intelligence/ingestion_orchestrator.py").read_text()
    finalize = source[source.index("def finalize_option_snapshot"):source.index("def publish_option_snapshot")]
    assert "FROM option_contract_snapshot" in finalize
    assert "snapshot_run_id=:run_id" in finalize
    assert "DELETE FROM option_contract_history history" in finalize
    assert "snapshot.option_symbol=history.option_symbol" in finalize
    assert "capture_status=:status" in finalize
    assert "WHERE quote_date = :capture_date" not in finalize


def test_split_options_entrypoint_uses_exact_cycle_lineage_and_parallel_derived_barrier():
    source = (ROOT / "scripts/ingest_options_data.py").read_text()
    assert "core._begin_fresh_option_lineage" in source
    assert "governed_snapshot_run_id=int(building[\"run_id\"])" in source
    assert "core._finalize_fresh_option_lineage" in source
    assert "core._run_fresh_option_derived_lanes" in source
    assert "derived_parallel_wall_seconds" in source
    assert "stale_daily_rows_pruned" in source


def test_dealer_parallelism_is_partitioned_by_symbol_and_result_order_is_deterministic():
    lock = threading.Lock()
    active = 0
    maximum_active = 0

    class FakeService:
        def run(self, symbol, as_of, **kwargs):
            nonlocal active, maximum_active
            with lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.025)
            with lock:
                active -= 1
            return SimpleNamespace(
                option_snapshot_date=as_of.isoformat(),
                source_contract_count=10,
                executable_contract_count=8,
                positioning_label="NEUTRAL",
                confidence_score=80.0,
            )

    orchestrator = DealerPositionRefreshOrchestrator(
        write_reports=False,
        service_factory=lambda policy: FakeService(),
    )
    symbols = ("AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOG", "TSLA", "AMD")
    profile = orchestrator.run(symbols, date(2026, 8, 17), continue_on_error=True, max_workers=4)

    assert maximum_active >= 2
    assert profile.refreshed_symbols == len(symbols)
    assert tuple(result.symbol for result in profile.results) == symbols


def test_derived_parallelism_keeps_market_governance_behind_join_barrier():
    source = (ROOT / "scripts/run_market_ingestion.py").read_text()
    helper = source[source.index("def _run_fresh_option_derived_lanes"):source.index("def _publish_fresh_option_lineage")]
    assert "ThreadPoolExecutor(max_workers=3" in helper
    assert "_build_fresh_option_volatility" in helper
    assert "_build_fresh_option_liquidity" in helper
    assert "_run_dealer_positioning" in helper
    assert "vol_future.result()" in helper
    assert "liq_future.result()" in helper
    assert "dealer_future.result()" in helper
