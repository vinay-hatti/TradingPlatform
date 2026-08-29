from __future__ import annotations

import threading
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from trading_ai.institutional_market_structure.refresh import DealerPositionRefreshOrchestrator
from trading_ai.scanner.options_market_data_ingestion.polygon_snapshot_provider import (
    PolygonOptionChainSnapshotProvider,
    PolygonSnapshotPolicy,
)

ROOT = Path(__file__).resolve().parents[2]


class _Response:
    status_code = 200
    def __init__(self, payload): self._payload = payload
    def raise_for_status(self): return None
    def json(self): return self._payload


def _payload(symbol: str):
    return {
        "results": [{
            "details": {
                "contract_type": "call",
                "expiration_date": "2026-09-18",
                "strike_price": 100.0,
                "ticker": f"O:{symbol}260918C00100000",
            },
            "last_quote": {"bid": 4.0, "ask": 4.2},
            "last_trade": {"price": 4.1},
            "day": {"volume": 10},
            "open_interest": 20,
            "implied_volatility": 0.3,
            "greeks": {"delta": 0.5, "gamma": 0.02, "theta": -0.05, "vega": 0.1},
            "underlying_asset": {"price": 100.0},
        }]
    }


def test_polygon_concurrent_symbol_capture_preserves_deterministic_output_and_global_profile():
    lock = threading.Lock(); active = 0; maximum_active = 0

    class Session:
        def get(self, url, params=None, timeout=None):
            nonlocal active, maximum_active
            symbol = url.rstrip("/").split("/")[-1]
            with lock:
                active += 1; maximum_active = max(maximum_active, active)
            time.sleep(0.02)
            with lock: active -= 1
            return _Response(_payload(symbol))

    provider = PolygonOptionChainSnapshotProvider(
        "key",
        as_of_date=date(2026, 8, 17),
        policy=PolygonSnapshotPolicy(
            minimum_dte=1,
            maximum_dte=180,
            requests_per_second=1000,
            network_workers=4,
        ),
        session=Session(),
    )
    batches = list(provider.iter_batches(symbols=("TSLA", "AAPL", "MSFT", "NVDA", "AMZN"), batch_size=100))
    assert maximum_active >= 2
    assert [b.metadata["symbol"] for b in batches] == ["AAPL", "AMZN", "MSFT", "NVDA", "TSLA"]
    profile = provider.performance_profile
    assert profile["execution_mode"] == "CONCURRENT_SYMBOL_CAPTURE_GLOBAL_RATE_LIMIT"
    assert profile["network_workers"] == 4
    assert profile["request_count"] == 5
    assert profile["requests_per_second_limit"] == 1000


def test_dealer_reverts_regressing_bulk_preload_and_surfaces_substage_timings():
    class FakeService:
        def __init__(self): self.last_profile = {}
        def run(self, symbol, as_of, **kwargs):
            self.last_profile = {
                "input_seconds": 1.0,
                "compute_seconds": 2.0,
                "persistence_seconds": 3.0,
                "persistence_commit_seconds": 2.5,
                "report_seconds": 0.5,
            }
            return SimpleNamespace(
                option_snapshot_date=as_of.isoformat(), source_contract_count=10,
                executable_contract_count=8, positioning_label="NEUTRAL", confidence_score=80.0,
            )

    profile = DealerPositionRefreshOrchestrator(
        write_reports=False, service_factory=lambda policy: FakeService()
    ).run(("AAPL", "MSFT"), date(2026, 8, 17), continue_on_error=True, max_workers=2)

    assert profile.preload_seconds == 0.0
    assert profile.execution_mode == "PARALLEL_SYMBOL_ISOLATED_PROFILED"
    assert profile.timing_totals["input_seconds"] == 2.0
    assert profile.timing_totals["compute_seconds"] == 4.0
    assert profile.timing_totals["persistence_seconds"] == 6.0
    assert profile.timing_totals["persistence_commit_seconds"] == 5.0


def test_split_options_entrypoint_enables_four_network_workers_and_records_capture_profile():
    parser_source = (ROOT / "scripts/run_market_ingestion.py").read_text()
    split_source = (ROOT / "scripts/ingest_options_data.py").read_text()
    assert '"--polygon-network-workers"' in parser_source
    assert 'default=4' in parser_source[parser_source.index('"--polygon-network-workers"'):parser_source.index('"--polygon-network-workers"') + 500]
    assert 'network_workers=max(1, int(getattr(args, "polygon_network_workers", 4)))' in split_source
    assert '"polygon_capture": polygon_profile' in split_source
    assert 'Polygon capture profile:' in split_source
    intraday = (ROOT / "scripts/m69_6_scheduled/run_intraday.sh").read_text()
    morning = (ROOT / "scripts/m69_6_scheduled/run_morning.sh").read_text()
    eod = (ROOT / "scripts/m69_6_scheduled/run_eod.sh").read_text()
    assert "--polygon-network-workers 1" in intraday
    assert "--polygon-network-workers 1" in morning
    assert "--polygon-network-workers 1" in eod


def test_global_rate_limiter_is_shared_not_per_worker():
    source = (ROOT / "src/trading_ai/scanner/options_market_data_ingestion/polygon_snapshot_provider.py").read_text()
    assert "self._throttle_lock = threading.Lock()" in source
    throttle = source[source.index("def _throttle(self)"):source.index("def _accept(self")]
    assert "with self._throttle_lock" in throttle
    assert "minimum_interval = 1.0 / self.policy.requests_per_second" in throttle
    assert "ThreadPoolExecutor" not in throttle
