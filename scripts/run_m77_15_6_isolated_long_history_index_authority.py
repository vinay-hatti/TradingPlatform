#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import date, timezone, datetime
from pathlib import Path

from trading_ai.historical_underlying_replay.long_history_index_authority import (
    continuity_audit,
    cross_symbol_session_audit,
    fetch_polygon_daily,
    normalize_rows,
    sha256_file,
    write_csv_atomic,
    write_json_atomic,
)

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_15_6_long_history_index_authority.json"
VERSION="M77.15.6-ISOLATED-LONG-HISTORY-INDEX-RESEARCH-AUTHORITY-1.0"
CONFIRM="MATERIALIZE_M77_15_6_ISOLATED_LONG_HISTORY_INDEX_AUTHORITY"

FIELDS=("symbol","polygon_ticker","date","open","high","low","close","volume","vwap","transactions","source_timestamp_ms")

def load_cfg():
    return json.loads(CFG.read_text())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","materialize","audit"))
    ap.add_argument("--confirm")
    ap.add_argument("--end-date")
    a=ap.parse_args()

    cfg=load_cfg()
    storage=ROOT/cfg["research_storage_root"]
    raw=ROOT/cfg["raw_storage"]
    norm=ROOT/cfg["normalized_storage"]
    manifests=ROOT/cfg["manifest_storage"]
    end=a.end_date or datetime.now(timezone.utc).date().isoformat()

    if a.mode=="preflight":
        print(json.dumps({
            "version":VERSION,
            "status":"READY",
            "confirmation_required":CONFIRM,
            "provider":cfg["source"],
            "targets":cfg["targets"],
            "requested_range":[cfg["start_date"],end],
            "storage_root":str(storage),
            "api_key_env":cfg["api_key_env"],
            "api_key_present":bool(os.getenv(cfg["api_key_env"])),
            "governance":{
                "isolated_research_storage":True,
                "production_price_history_writes":False,
                "database_writes":False,
                "fallback_tickers_prohibited":True,
                "production_authority_effect":False
            }
        },indent=2))
        return

    if a.mode=="materialize":
        if a.confirm!=CONFIRM:
            raise SystemExit(f"confirmation required: {CONFIRM}")
        api_key=os.getenv(cfg["api_key_env"])
        if not api_key:
            raise SystemExit(f"missing required environment variable: {cfg['api_key_env']}")

        all_series={}
        target_manifests={}
        for logical,meta in cfg["targets"].items():
            ticker=meta["requested_polygon_ticker"]
            raw_dir=raw/logical
            results,pages=fetch_polygon_daily(
                ticker=ticker,
                start=cfg["start_date"],
                end=end,
                api_key=api_key,
                raw_dir=raw_dir,
            )
            rows=normalize_rows(logical,ticker,results)
            if not rows:
                raise SystemExit(
                    f"no Polygon aggregate rows returned for {logical} ({ticker}); "
                    "fallback ticker substitution is prohibited"
                )
            out=norm/f"{logical}_daily.csv"
            write_csv_atomic(out,rows,list(FIELDS))
            audit=continuity_audit(rows)
            target_manifests[logical]={
                "logical_symbol":logical,
                "polygon_ticker":ticker,
                "requested_start":cfg["start_date"],
                "requested_end":end,
                "normalized_path":str(out),
                "normalized_sha256":sha256_file(out),
                "raw_pages":pages,
                "continuity_audit":audit,
            }
            all_series[logical]=rows

        cross=cross_symbol_session_audit(all_series)
        manifest={
            "version":VERSION,
            "status":"READY",
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "provider":"POLYGON",
            "provider_mode":"REST_AGGREGATES_DAILY",
            "requested_range":[cfg["start_date"],end],
            "targets":target_manifests,
            "cross_symbol_session_audit":cross,
            "governance":{
                "research_storage_root":str(storage),
                "database_writes":False,
                "production_price_history_writes":False,
                "production_ingestion_changes":False,
                "production_authority_effect":False,
                "fallback_tickers_prohibited":True,
                "source_provenance_checksums":True,
            },
            "next_step":"CERTIFY_LONG_HISTORY_AUTHORITY_THEN_BUILD_M77_15_7_REPLICATION"
        }
        manifest_path=manifests/"latest.json"
        write_json_atomic(manifest_path,manifest)
        print(json.dumps({
            "version":VERSION,
            "status":"READY",
            "manifest":str(manifest_path),
            "target_rows":{k:v["continuity_audit"]["row_count"] for k,v in target_manifests.items()},
            "target_ranges":{
                k:[v["continuity_audit"]["first_date"],v["continuity_audit"]["last_date"]]
                for k,v in target_manifests.items()
            },
            "common_session_count":cross["common_session_count"],
            "production_authority_effect":False
        },indent=2))
        return

    # audit mode
    manifest=manifests/"latest.json"
    if not manifest.exists():
        raise SystemExit("No M77.15.6 materialized authority manifest found")
    x=json.loads(manifest.read_text())
    print(json.dumps({
        "version":x["version"],
        "status":x["status"],
        "requested_range":x["requested_range"],
        "target_ranges":{
            k:[
                v["continuity_audit"]["first_date"],
                v["continuity_audit"]["last_date"],
                v["continuity_audit"]["row_count"],
            ]
            for k,v in x["targets"].items()
        },
        "cross_symbol_session_audit":x["cross_symbol_session_audit"],
        "next_step":x["next_step"],
        "production_authority_effect":False
    },indent=2))

if __name__=="__main__":
    main()
