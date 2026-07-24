from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
from typing import Iterable

from trading_ai.config import settings
from trading_ai.database import SessionLocal
from trading_ai.market.downloader import MarketDownloader
from trading_ai.scanner.options_market_data_ingestion import IngestionManifestStore, OptionHistoryIngestionService
from trading_ai.scanner.options_market_data_ingestion.polygon_snapshot_provider import PolygonOptionChainSnapshotProvider, PolygonSnapshotPolicy
from trading_ai.scanner.options_market_data_ingestion.serialization import write_ingestion_profile_json

DEFAULT_UNIVERSE_FILE = Path("data/universe/us_listed_equities_etfs.csv")
_SYMBOL_COLUMNS = ("symbol", "provider_symbol", "ticker")
_ACTIVE_VALUES = {"1", "true", "yes", "y", "active"}

def _normalize_symbols(values: Iterable[str]) -> tuple[str, ...]:
    out=[]; seen=set()
    for value in values:
        symbol=str(value or "").strip().upper()
        if not symbol or symbol.startswith("#") or symbol in seen: continue
        seen.add(symbol); out.append(symbol)
    if not out: raise ValueError("No valid symbols were resolved for market ingestion.")
    return tuple(out)

def _read_delimited_symbol_file(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample=handle.read(8192); handle.seek(0)
        try: dialect=csv.Sniffer().sniff(sample, delimiters=",\t;|")
        except csv.Error: dialect=csv.excel
        rows=list(csv.reader(handle,dialect))
    if not rows: raise ValueError(f"Symbol file is empty: {path}")
    header=[c.strip().lower() for c in rows[0]]
    symbol_index=next((header.index(c) for c in _SYMBOL_COLUMNS if c in header),None)
    active_index=header.index("active") if "active" in header else None
    if symbol_index is not None:
        values=[]
        for row in rows[1:]:
            if symbol_index>=len(row): continue
            if active_index is not None and active_index<len(row):
                active=row[active_index].strip().lower()
                if active and active not in _ACTIVE_VALUES: continue
            values.append(row[symbol_index])
        return _normalize_symbols(values)
    return _normalize_symbols(cell for row in rows for cell in row)

def load_symbols_file(path_value: str|Path)->tuple[str,...]:
    path=Path(path_value).expanduser()
    if not path.is_file(): raise FileNotFoundError(f"Symbol file not found: {path}")
    if path.suffix.lower() in {".csv",".tsv"}: return _read_delimited_symbol_file(path)
    tokens=[]
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line=line.strip()
        if not line or line.startswith("#"): continue
        tokens.extend(part.strip() for part in line.replace("\t",",").split(","))
    return _normalize_symbols(tokens)

def resolve_symbols(symbols, symbols_file, universe_file=DEFAULT_UNIVERSE_FILE):
    if symbols: return _normalize_symbols(symbols.split(","))
    if symbols_file: return load_symbols_file(symbols_file)
    return load_symbols_file(universe_file)

def build_parser():
    p=argparse.ArgumentParser(description="Authoritative Yahoo OHLCV + Polygon options ingestion pipeline.")
    g=p.add_mutually_exclusive_group(); g.add_argument("--symbols"); g.add_argument("--symbols-file")
    p.add_argument("--universe-file",default=str(DEFAULT_UNIVERSE_FILE))
    p.add_argument("--data-scope",choices=["underlying","options","all"],default="all")
    p.add_argument("--start"); p.add_argument("--end"); p.add_argument("--lookback-days",type=int,default=730)
    p.add_argument("--max-workers",type=int,default=4,help="Concurrent Yahoo OHLCV workers. Default: 4")
    p.add_argument("--request-interval",type=float,default=1.0,help="Global minimum seconds between Yahoo requests. Default: 1.0")
    p.add_argument("--max-retries",type=int,default=5); p.add_argument("--initial-backoff",type=float,default=30.0); p.add_argument("--max-backoff",type=float,default=300.0)
    p.add_argument("--force-refresh",action="store_true"); p.add_argument("--continue-on-error",action="store_true")
    p.add_argument("--options-minimum-dte",type=int,default=14); p.add_argument("--options-maximum-dte",type=int,default=90)
    p.add_argument("--options-minimum-open-interest",type=int,default=1); p.add_argument("--options-minimum-volume",type=int,default=0)
    p.add_argument("--options-maximum-strike-distance-pct",type=float,default=.40); p.add_argument("--polygon-requests-per-second",type=float,default=4.0)
    p.add_argument("--options-batch-size",type=int,default=5000); p.add_argument("--options-manifest",default="reports/market_ingestion/options_manifest.json")
    p.add_argument("--options-report",default="reports/market_ingestion/options_latest.json")
    return p

def main(argv=None):
    args=build_parser().parse_args(argv)
    symbols=resolve_symbols(args.symbols,args.symbols_file,args.universe_file)
    print(f"Market ingestion universe: {len(symbols)} symbols")
    print(f"OHLCV concurrency: workers={args.max_workers}, request_interval={args.request_interval:.2f}s")
    failed=0
    if args.data_scope in {"underlying","all"}:
        results=MarketDownloader(max_workers=args.max_workers,request_interval_seconds=args.request_interval,max_retries=args.max_retries,initial_backoff_seconds=args.initial_backoff,max_backoff_seconds=args.max_backoff).run_bulk_download(symbols=symbols,start=args.start,end=args.end,lookback_days=args.lookback_days,force_refresh=args.force_refresh,fail_on_error=not args.continue_on_error)
        failed += sum(not r.success for r in results)
    if args.data_scope in {"options","all"}:
        api_key=getattr(settings,"polygon_api_key",None)
        if not api_key: raise RuntimeError("POLYGON_API_KEY is not configured")
        capture_date=date.fromisoformat((args.end or date.today().isoformat())[:10])
        provider=PolygonOptionChainSnapshotProvider(str(api_key),as_of_date=capture_date,policy=PolygonSnapshotPolicy(minimum_dte=args.options_minimum_dte,maximum_dte=args.options_maximum_dte,minimum_open_interest=args.options_minimum_open_interest,minimum_volume=args.options_minimum_volume,maximum_strike_distance_pct=args.options_maximum_strike_distance_pct,requests_per_second=args.polygon_requests_per_second))
        manifest=IngestionManifestStore(args.options_manifest)
        if args.force_refresh: manifest.reset()
        session=SessionLocal()
        try:
            profile=OptionHistoryIngestionService(session,provider,manifest_store=manifest).run(symbols=symbols,batch_size=args.options_batch_size,resume=not args.force_refresh,fail_fast=not args.continue_on_error)
        finally: session.close()
        write_ingestion_profile_json(profile,args.options_report)
        failed += profile.failed_batches
        print(f"Options ingestion: {profile.valid_records} valid, {profile.inserted_records} inserted, {profile.updated_records} updated, {profile.failed_batches} failed batches")
    return 0 if failed==0 or args.continue_on_error else 1

if __name__ == "__main__": raise SystemExit(main())
