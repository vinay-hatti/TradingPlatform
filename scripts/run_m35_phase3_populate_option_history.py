from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.scanner.options_market_data_ingestion import (
    CsvOptionHistoryProvider,
    IngestionManifestStore,
    OptionHistoryIngestionService,
)
from trading_ai.scanner.options_market_data_ingestion.serialization import (
    write_ingestion_profile_json,
)


def load_symbols(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        symbol_key = next(
            (name for name in fields if name.strip().lower() == "symbol"),
            None,
        )
        if symbol_key is None:
            raise ValueError(f"CSV must contain symbol column: {path}")
        active_key = next(
            (name for name in fields if name.strip().lower() == "active"),
            None,
        )
        result = []
        for row in reader:
            if active_key is not None:
                active = str(row.get(active_key, "")).strip().lower()
                if active and active not in {"1", "true", "yes", "y"}:
                    continue
            symbol = str(row.get(symbol_key, "")).strip().upper()
            if symbol:
                result.append(symbol)
    return sorted(set(result))


def parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate option_contract_history from historical CSV files."
    )
    parser.add_argument(
        "--csv",
        action="append",
        required=True,
        help="Historical option CSV path. Repeat for multiple files.",
    )
    parser.add_argument("--symbols")
    parser.add_argument("--canonical-universe", action="store_true")
    parser.add_argument(
        "--canonical-csv",
        default="data/universe/us_listed_equities_etfs.csv",
    )
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--batch-size", type=int, default=5_000)
    parser.add_argument(
        "--manifest",
        default="reports/m35/phase3/ingestion/manifest.json",
    )
    parser.add_argument(
        "--report",
        default="reports/m35/phase3/ingestion/ingestion_run.json",
    )
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    if args.canonical_universe:
        symbols = load_symbols(Path(args.canonical_csv))
    elif args.symbols:
        symbols = [
            symbol.strip().upper()
            for symbol in args.symbols.split(",")
            if symbol.strip()
        ]
    else:
        symbols = None

    manifest = IngestionManifestStore(args.manifest)
    if args.restart:
        manifest.reset()

    provider = CsvOptionHistoryProvider(args.csv)
    session = SessionLocal()
    try:
        profile = OptionHistoryIngestionService(
            session,
            provider,
            manifest_store=manifest,
        ).run(
            symbols=symbols,
            start_date=parse_date(args.start),
            end_date=parse_date(args.end),
            batch_size=args.batch_size,
            resume=not args.restart,
            fail_fast=args.fail_fast,
        )
    finally:
        session.close()

    report_path = write_ingestion_profile_json(profile, args.report)

    print("=" * 70)
    print("Milestone 35 Phase 3 Option History Population")
    print("=" * 70)
    print(f"Source                          {profile.source_name:>12}")
    print(f"Batches Processed               {profile.batch_count:>12}")
    print(f"Batches Resumed                 {profile.resumed_batches:>12}")
    print(f"Failed Batches                  {profile.failed_batches:>12}")
    print(f"Input Records                   {profile.input_records:>12}")
    print(f"Valid Records                   {profile.valid_records:>12}")
    print(f"Rejected Records                {profile.rejected_records:>12}")
    print(f"Inserted Records                {profile.inserted_records:>12}")
    print(f"Updated Records                 {profile.updated_records:>12}")
    print(f"Skipped/Duplicates              {profile.skipped_records:>12}")
    print(f"Manifest                        {args.manifest}")
    print(f"Run Report                      {report_path}")


if __name__ == "__main__":
    main()
