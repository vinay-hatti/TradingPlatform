#!/usr/bin/env python3
from __future__ import annotations

import argparse,json,os
from datetime import datetime,timezone
from pathlib import Path

from trading_ai.historical_underlying_replay.long_history_index_authority import (
    continuity_audit,
    fetch_polygon_daily,
    normalize_rows,
    sha256_file,
    write_csv_atomic,
    write_json_atomic,
)

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_15_6_4_polygon_coverage_lineage.json"
VERSION="M77.15.6.4-POLYGON-COVERAGE-SYMBOL-LINEAGE-RESOLUTION-1.0"
CONFIRM="RUN_M77_15_6_4_POLYGON_COVERAGE_LINEAGE_DIAGNOSTIC"

FIELDS=("symbol","polygon_ticker","date","open","high","low","close","volume","vwap","transactions","source_timestamp_ms")

def load_cfg():
    return json.loads(CFG.read_text())

def index_rows(rows):
    return {r["date"]:r for r in rows}

def stitch_qqq(qqq,qqqq):
    # Deterministic frozen lineage:
    # QQQ <= 2004-11-30
    # QQQQ 2004-12-01..2011-03-22
    # QQQ >= 2011-03-23
    q=index_rows(qqq)
    q4=index_rows(qqqq)
    out=[]
    provenance=[]
    dates=sorted(set(q)|set(q4))
    for d in dates:
        if d <= "2004-11-30":
            src="QQQ"; row=q.get(d)
        elif d <= "2011-03-22":
            src="QQQQ"; row=q4.get(d)
        else:
            src="QQQ"; row=q.get(d)
        if row:
            x=dict(row)
            x["symbol"]="QQQ_LINEAGE"
            x["polygon_ticker"]=src
            out.append(x)
            provenance.append({"date":d,"source_ticker":src})
    return out,provenance

def overlap_audit(a,b):
    ai=index_rows(a); bi=index_rows(b)
    overlap=sorted(set(ai)&set(bi))
    close_diffs=[]
    for d in overlap:
        ac=ai[d].get("close"); bc=bi[d].get("close")
        if ac is not None and bc is not None:
            close_diffs.append({"date":d,"abs_close_diff":abs(float(ac)-float(bc))})
    return {
        "overlap_session_count":len(overlap),
        "overlap_first_date":overlap[0] if overlap else None,
        "overlap_last_date":overlap[-1] if overlap else None,
        "max_abs_close_diff":max((x["abs_close_diff"] for x in close_diffs),default=None),
        "sample":close_diffs[:20],
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","run","report-json"))
    ap.add_argument("--confirm")
    ap.add_argument("--end-date")
    a=ap.parse_args()

    cfg=load_cfg()
    end=a.end_date or datetime.now(timezone.utc).date().isoformat()
    start=cfg["requested_range"][0]
    base=ROOT/cfg["storage_root"]
    raw_root=ROOT/cfg["raw_storage"]
    norm_root=ROOT/cfg["normalized_storage"]
    manifests=ROOT/cfg["manifest_storage"]

    if a.mode=="preflight":
        print(json.dumps({
            "version":VERSION,
            "status":"READY",
            "confirmation_required":CONFIRM,
            "provider":"POLYGON",
            "requested_range":[start,end],
            "diagnostic_scope":cfg["diagnostic_scope"],
            "governance":{
                "diagnostic_only":True,
                "canonical_authorities_mutated":False,
                "database_writes":False,
                "production_price_history_writes":False,
                "production_authority_effect":False
            }
        },indent=2))
        return

    if a.mode=="run":
        if a.confirm!=CONFIRM:
            raise SystemExit(f"confirmation required: {CONFIRM}")
        key=os.getenv(cfg["api_key_env"])
        if not key:
            raise SystemExit(f"missing required environment variable: {cfg['api_key_env']}")

        series={}
        manifests_by_symbol={}
        for ticker in ("SPY","QQQ","QQQQ","IWM"):
            results,pages=fetch_polygon_daily(
                ticker=ticker,start=start,end=end,api_key=key,raw_dir=raw_root/ticker
            )
            rows=normalize_rows(ticker,ticker,results)
            series[ticker]=rows
            out=norm_root/f"{ticker}_daily.csv"
            if rows:
                write_csv_atomic(out,rows,list(FIELDS))
                audit=continuity_audit(rows)
                sha=sha256_file(out)
            else:
                audit=continuity_audit([])
                sha=None
            manifests_by_symbol[ticker]={
                "ticker":ticker,
                "rows":len(rows),
                "first_date":audit["first_date"],
                "last_date":audit["last_date"],
                "normalized_path":str(out) if rows else None,
                "normalized_sha256":sha,
                "raw_pages":pages,
                "continuity_audit":audit,
            }

        stitched,prov=stitch_qqq(series["QQQ"],series["QQQQ"])
        stitched_path=norm_root/"QQQ_LINEAGE_daily.csv"
        if stitched:
            write_csv_atomic(stitched_path,stitched,list(FIELDS))
        stitched_audit=continuity_audit(stitched)

        qqq_overlap=overlap_audit(series["QQQ"],series["QQQQ"])

        # Coverage classification - descriptive, not authority certification.
        spy=manifests_by_symbol["SPY"]
        q4=manifests_by_symbol["QQQQ"]
        iwm=manifests_by_symbol["IWM"]

        findings={
            "SPY":{
                "coverage_floor":spy["first_date"],
                "rows":spy["rows"],
                "classification":"MATERIAL_LONG_HISTORY_BUT_NOT_2000_AUTHORITY"
                    if spy["rows"]>=5000 else "INSUFFICIENT_LONG_HISTORY",
            },
            "QQQ":{
                "qqq_rows":manifests_by_symbol["QQQ"]["rows"],
                "qqqq_rows":q4["rows"],
                "stitched_rows":stitched_audit["row_count"],
                "stitched_first_date":stitched_audit["first_date"],
                "stitched_last_date":stitched_audit["last_date"],
                "lineage_overlap_audit":qqq_overlap,
                "classification":"LINEAGE_STITCH_MATERIALLY_EXTENDS_HISTORY"
                    if q4["rows"]>0 and stitched_audit["row_count"]>manifests_by_symbol["QQQ"]["rows"]
                    else "NO_MATERIAL_LINEAGE_EXTENSION",
            },
            "IWM":{
                "coverage_floor":iwm["first_date"],
                "rows":iwm["rows"],
                "known_fund_inception_date":cfg["diagnostic_scope"]["IWM"]["known_fund_inception_date"],
                "classification":"POLYGON_COVERAGE_GAP_RELATIVE_TO_KNOWN_FUND_INCEPTION"
                    if iwm["first_date"] and iwm["first_date"]>"2001-01-01"
                    else "MATERIAL_LONG_HISTORY_AVAILABLE",
            },
        }

        manifest={
            "version":VERSION,
            "status":"READY",
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "provider":"POLYGON",
            "requested_range":[start,end],
            "source_series":manifests_by_symbol,
            "qqq_lineage":{
                "frozen_segments":cfg["diagnostic_scope"]["QQQ"]["expected_segments"],
                "stitched_path":str(stitched_path) if stitched else None,
                "stitched_sha256":sha256_file(stitched_path) if stitched else None,
                "stitched_continuity_audit":stitched_audit,
                "provenance_row_count":len(prov),
            },
            "findings":findings,
            "governance":{
                "diagnostic_only":True,
                "canonical_authorities_mutated":False,
                "database_writes":False,
                "production_price_history_writes":False,
                "production_authority_effect":False,
                "no_threshold_relaxation":True,
            },
            "next_step":"REVIEW_SPY_MATERIAL_HISTORY_QQQ_LINEAGE_AND_IWM_POLYGON_GAP_BEFORE_ANY_M77_15_7_REPLICATION"
        }
        mpath=manifests/"latest.json"
        write_json_atomic(mpath,manifest)
        print(json.dumps({
            "version":VERSION,
            "status":"READY",
            "manifest":str(mpath),
            "symbol_ranges":{
                k:[v["first_date"],v["last_date"],v["rows"]]
                for k,v in manifests_by_symbol.items()
            },
            "qqq_stitched_range":[
                stitched_audit["first_date"],stitched_audit["last_date"],stitched_audit["row_count"]
            ],
            "findings":findings,
            "production_authority_effect":False
        },indent=2))
        return

    m=manifests/"latest.json"
    if not m.exists():
        raise SystemExit("Run M77.15.6.4 diagnostic first")
    print(m.read_text(),end="")

if __name__=="__main__":
    main()
