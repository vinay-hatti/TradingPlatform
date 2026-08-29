#!/usr/bin/env python3
from __future__ import annotations

import argparse,json,os
from datetime import datetime,timezone
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
CFG=ROOT/"config/m77/m77_15_6_3_tradable_proxy_authority.json"
VERSION="M77.15.6.3-POLYGON-LONG-HISTORY-TRADABLE-PROXY-RESEARCH-AUTHORITY-1.0"
CONFIRM="MATERIALIZE_M77_15_6_3_LONG_HISTORY_TRADABLE_PROXY_AUTHORITY"

FIELDS=(
    "research_target","research_instrument","authority_type","proxy_for",
    "symbol","polygon_ticker","date","open","high","low","close","volume",
    "vwap","transactions","source_timestamp_ms"
)

def load_cfg():
    return json.loads(CFG.read_text())

def decorate(rows,research_target,research_instrument):
    out=[]
    for r in rows:
        x=dict(r)
        x["research_target"]=research_target
        x["research_instrument"]=research_instrument
        x["authority_type"]="LONG_HISTORY_TRADABLE_PROXY"
        x["proxy_for"]=research_target
        out.append(x)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","materialize","audit"))
    ap.add_argument("--confirm")
    ap.add_argument("--end-date")
    a=ap.parse_args()

    cfg=load_cfg()
    end=a.end_date or datetime.now(timezone.utc).date().isoformat()
    start=cfg["requested_start_date"]
    root=ROOT/cfg["storage_root"]
    raw_root=ROOT/cfg["raw_storage"]
    norm_root=ROOT/cfg["normalized_storage"]
    manifests=ROOT/cfg["manifest_storage"]

    if a.mode=="preflight":
        print(json.dumps({
            "version":VERSION,
            "status":"READY",
            "confirmation_required":CONFIRM,
            "provider":cfg["provider"],
            "authority_type":cfg["authority_type"],
            "requested_range":[start,end],
            "targets":cfg["targets"],
            "storage_root":str(root),
            "api_key_env":cfg["api_key_env"],
            "api_key_present":bool(os.getenv(cfg["api_key_env"])),
            "governance":{
                "explicit_proxy_authority":True,
                "proxy_may_be_represented_as_index":False,
                "canonical_index_authority_overwrite":False,
                "fallback_substitution":False,
                "database_writes":False,
                "production_price_history_writes":False,
                "production_ingestion_changes":False,
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
        for target,meta in cfg["targets"].items():
            instrument=meta["research_instrument"]
            ticker=meta["polygon_ticker"]
            results,pages=fetch_polygon_daily(
                ticker=ticker,
                start=start,
                end=end,
                api_key=api_key,
                raw_dir=raw_root/target,
            )
            base_rows=normalize_rows(instrument,ticker,results)
            if not base_rows:
                raise SystemExit(
                    f"no Polygon aggregate rows returned for explicit proxy "
                    f"{target}->{instrument} ({ticker})"
                )
            rows=decorate(base_rows,target,instrument)
            out=norm_root/f"{target}_{instrument}_daily.csv"
            write_csv_atomic(out,rows,list(FIELDS))
            audit=continuity_audit(rows)

            target_manifests[target]={
                "research_target":target,
                "research_instrument":instrument,
                "proxy_for":target,
                "authority_type":"LONG_HISTORY_TRADABLE_PROXY",
                "polygon_ticker":ticker,
                "requested_start":start,
                "requested_end":end,
                "normalized_path":str(out),
                "normalized_sha256":sha256_file(out),
                "raw_pages":pages,
                "continuity_audit":audit,
                "certification_start_no_later_than":meta["certification_start_no_later_than"],
                "minimum_rows":meta["minimum_rows"],
            }
            all_series[target]=rows

        cross=cross_symbol_session_audit(all_series)
        manifest={
            "version":VERSION,
            "status":"READY",
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "provider":"POLYGON",
            "authority_type":"LONG_HISTORY_TRADABLE_PROXY",
            "requested_range":[start,end],
            "targets":target_manifests,
            "cross_symbol_session_audit":cross,
            "governance":{
                "canonical_index_authority_overwrite":False,
                "proxy_may_be_represented_as_index":False,
                "fallback_substitution":False,
                "database_writes":False,
                "production_price_history_writes":False,
                "production_ingestion_changes":False,
                "production_authority_effect":False,
                "source_provenance_checksums":True
            },
            "next_step":"CERTIFY_M77_15_6_3_THEN_BUILD_M77_15_7_LONG_HISTORY_REPLICATION"
        }
        manifest_path=manifests/"latest.json"
        write_json_atomic(manifest_path,manifest)
        print(json.dumps({
            "version":VERSION,
            "status":"READY",
            "manifest":str(manifest_path),
            "authority_type":"LONG_HISTORY_TRADABLE_PROXY",
            "target_rows":{k:v["continuity_audit"]["row_count"] for k,v in target_manifests.items()},
            "target_ranges":{
                k:[v["continuity_audit"]["first_date"],v["continuity_audit"]["last_date"]]
                for k,v in target_manifests.items()
            },
            "common_session_count":cross["common_session_count"],
            "production_authority_effect":False
        },indent=2))
        return

    manifest=manifests/"latest.json"
    if not manifest.exists():
        raise SystemExit("No M77.15.6.3 materialized proxy authority manifest found")
    x=json.loads(manifest.read_text())
    print(json.dumps({
        "version":x["version"],
        "status":x["status"],
        "authority_type":x["authority_type"],
        "requested_range":x["requested_range"],
        "target_ranges":{
            k:[
                v["research_instrument"],
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
