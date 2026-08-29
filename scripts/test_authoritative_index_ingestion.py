from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from trading_ai.market.instruments import CanonicalInstrumentRegistry
from trading_ai.market.providers.polygon_index import PolygonIndexHistoricalProvider
from trading_ai.scanner.options_market_data_ingestion.polygon_snapshot_provider import (
    PolygonOptionChainSnapshotProvider,
    PolygonSnapshotPolicy,
)


class FakeAggClient:
    def __init__(self) -> None:
        self.calls = []

    def get_aggs(self, **kwargs):
        self.calls.append(kwargs)
        return [
            SimpleNamespace(
                timestamp=1_700_000_000_000,
                open=5000,
                high=5010,
                low=4990,
                close=5005,
                volume=None,
            )
        ]


class FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {"results": []}


class FakeSession:
    def __init__(self) -> None:
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        return FakeResponse()


def main() -> None:
    registry = CanonicalInstrumentRegistry.from_files(
        (
            Path("data/universe/us_listed_equities_etfs.csv"),
            Path("data/universe/us_market_indices.csv"),
        )
    )
    assert registry.get("SPX").price_ticker == "I:SPX"
    assert registry.get("NDX").options_snapshot_ticker == "I:NDX"
    assert registry.get("RUT").options_reference_ticker == "RUT"
    assert registry.get("SPX").volume_applicable is False
    assert registry.get("AAPL").price_ticker == "AAPL"

    client = FakeAggClient()
    provider = PolygonIndexHistoricalProvider(
        {"SPX": "I:SPX"}, api_key="test", client=client
    )
    bars = provider.fetch_history("SPX", "2026-07-01", "2026-07-25")
    assert client.calls[0]["ticker"] == "I:SPX"
    assert bars[0].symbol == "SPX"
    assert bars[0].volume == 0.0

    session = FakeSession()
    snapshot = PolygonOptionChainSnapshotProvider(
        "test",
        as_of_date=date(2026, 7, 25),
        policy=PolygonSnapshotPolicy(requests_per_second=1000),
        session=session,
        sleep=lambda _: None,
        symbol_resolver=lambda symbol: {"SPX": "I:SPX"}[symbol],
    )
    assert list(snapshot.iter_batches(symbols=("SPX",))) == []
    assert session.calls[0][0].endswith("/I:SPX")

    with TemporaryDirectory() as temp_dir:
        custom = Path(temp_dir) / "indices.csv"
        custom.write_text(
            "canonical_symbol,name,asset_class,provider,price_ticker,"
            "options_snapshot_ticker,options_reference_ticker,options_eligible,active\n"
            "SPX,S&P 500 Index,INDEX,POLYGON,I:SPX,I:SPX,SPX,true,true\n",
            encoding="utf-8",
        )
        custom_registry = CanonicalInstrumentRegistry.from_files((custom,))
        assert custom_registry.select(asset_classes=("INDEX",))[0].canonical_symbol == "SPX"

    print("Authoritative index ingestion assertions passed.")


if __name__ == "__main__":
    main()
