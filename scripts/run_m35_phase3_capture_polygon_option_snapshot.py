from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from trading_ai.config import settings
from trading_ai.database import SessionLocal
from trading_ai.scanner.options_market_data_ingestion import IngestionManifestStore, OptionHistoryIngestionService
from trading_ai.scanner.options_market_data_ingestion.polygon_csv_sink import CsvRecordingOptionHistoryProvider
from trading_ai.scanner.options_market_data_ingestion.polygon_snapshot_provider import PolygonOptionChainSnapshotProvider, PolygonSnapshotPolicy
from trading_ai.scanner.options_market_data_ingestion.serialization import write_ingestion_profile_json


def load_symbols(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        symbol_key = next((name for name in fields if name.strip().lower() == "symbol"), None)
        if symbol_key is None:
            raise ValueError(f"CSV must contain a symbol column: {path}")
        active_key = next((name for name in fields if name.strip().lower() == "active"), None)
        symbols = []
        for row in reader:
            if active_key:
                active = str(row.get(active_key, "")).strip().lower()
                if active and active not in {"1", "true", "yes", "y"}:
                    continue
            symbol = str(row.get(symbol_key, "")).strip().upper()
            if symbol:
                symbols.append(symbol)
        return sorted(set(symbols))


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture Polygon option-chain snapshots for the canonical universe.")
    parser.add_argument("--canonical-csv", default="data/universe/us_listed_equities_etfs.csv")
    parser.add_argument("--symbols", help="Optional comma-separated override")
    parser.add_argument("--capture-date", default=date.today().isoformat())
    parser.add_argument("--output-csv", default="data/options/historical_options.csv")
    parser.add_argument("--manifest", default="reports/m35/phase3/polygon_snapshot/manifest.json")
    parser.add_argument("--report", default="reports/m35/phase3/polygon_snapshot/run.json")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--minimum-dte", type=int, default=7)
    parser.add_argument("--maximum-dte", type=int, default=365)
    parser.add_argument("--minimum-open-interest", type=int, default=1)
    parser.add_argument("--minimum-volume", type=int, default=0)
    parser.add_argument("--maximum-strike-distance-pct", type=float, default=0.40)
    parser.add_argument("--requests-per-second", type=float, default=4.0)
    parser.add_argument("--csv-only", action="store_true")
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    api_key = getattr(settings, "polygon_api_key", None)
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY is not configured")
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] if args.symbols else load_symbols(Path(args.canonical_csv))
    capture_date = date.fromisoformat(args.capture_date)
    policy = PolygonSnapshotPolicy(
        minimum_dte=args.minimum_dte,
        maximum_dte=args.maximum_dte,
        minimum_open_interest=args.minimum_open_interest,
        minimum_volume=args.minimum_volume,
        maximum_strike_distance_pct=args.maximum_strike_distance_pct,
        requests_per_second=args.requests_per_second,
    )
    provider = PolygonOptionChainSnapshotProvider(str(api_key), as_of_date=capture_date, policy=policy)
    provider = CsvRecordingOptionHistoryProvider(provider, args.output_csv, append=not args.restart)
    manifest = IngestionManifestStore(args.manifest)
    if args.restart:
        manifest.reset()
        output = Path(args.output_csv)
        if output.exists():
            output.unlink()

    if args.csv_only:
        batches = records = 0
        for batch in provider.iter_batches(symbols=symbols, batch_size=args.batch_size):
            batches += 1
            records += len(batch.records)
        print(f"Captured {records} records in {batches} batches to {args.output_csv}")
        return

    session = SessionLocal()
    try:
        profile = OptionHistoryIngestionService(session, provider, manifest_store=manifest).run(
            symbols=symbols,
            batch_size=args.batch_size,
            resume=not args.restart,
            fail_fast=args.fail_fast,
        )
    finally:
        session.close()
    report = write_ingestion_profile_json(profile, args.report)
    print("=" * 72)
    print("Milestone 35 Phase 3 Polygon Option Snapshot Capture")
    print("=" * 72)
    print(f"Canonical symbols     : {len(symbols)}")
    print(f"Processed batches     : {profile.batch_count}")
    print(f"Resumed batches       : {profile.resumed_batches}")
    print(f"Failed batches        : {profile.failed_batches}")
    print(f"Input records         : {profile.input_records}")
    print(f"Valid records         : {profile.valid_records}")
    print(f"Rejected records      : {profile.rejected_records}")
    print(f"Inserted records      : {profile.inserted_records}")
    print(f"Updated records       : {profile.updated_records}")
    print(f"CSV                    : {args.output_csv}")
    print(f"Report                 : {report}")


if __name__ == "__main__":
    main()
