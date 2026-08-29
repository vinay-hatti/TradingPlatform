#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import tempfile
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import text
from trading_ai.database.session import SessionLocal

VERSION="M77.20.4-PROSPECTIVE-F071-FEATURE-MATERIALIZATION-IMMUTABLE-SHADOW-CAPTURE-AUTHORITY-1.0"
EARLIEST_AUTHORIZED_DATE="2026-08-24"

class F071Error(RuntimeError):
    pass

def R(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def J(p):
    with Path(p).open("r",encoding="utf-8") as f:
        return json.load(f)

def H(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):
            h.update(c)
    return h.hexdigest()

def semantic_hash(obj):
    raw=json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def atomic(path,data:bytes):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def normalize_hist(rows):
    by_symbol=defaultdict(list)
    for r in rows:
        sym=str(r["symbol"]).upper()
        d=str(r["date"])[:10]
        c=float(r["close"])
        if c<=0:
            continue
        by_symbol[sym].append((d,c))
    out={}
    for sym,items in by_symbol.items():
        items.sort()
        dedup=[]
        for d,c in items:
            if dedup and dedup[-1][0]==d:
                if abs(dedup[-1][1]-c)>1e-12*max(1.0,abs(c),abs(dedup[-1][1])):
                    raise F071Error(f"{sym}: conflicting price_history close on {d}")
                continue
            dedup.append((d,c))
        out[sym]=dedup
    return out

def end_index(hist,as_of):
    dates=[d for d,_ in hist]
    i=bisect.bisect_right(dates,as_of)-1
    return i if i>=0 else None

def component(hist,bench,as_of,sessions):
    i=end_index(hist,as_of)
    j=end_index(bench,as_of)
    if i is None or j is None:
        return None,"NO_AS_OF_OR_PRIOR_CLOSE",None,None
    sym_end=hist[i][0]
    bench_end=bench[j][0]
    if sym_end!=bench_end:
        return None,"END_SESSION_MISMATCH",sym_end,bench_end
    if i-sessions<0 or j-sessions<0:
        return None,"INSUFFICIENT_TRAILING_SESSIONS",sym_end,bench_end
    s0=hist[i-sessions][1]
    b0=bench[j-sessions][1]
    if not s0 or not b0:
        return None,"INVALID_TRAILING_BASE_CLOSE",sym_end,bench_end
    sr=hist[i][1]/s0-1.0
    br=bench[j][1]/b0-1.0
    return sr-br,"AVAILABLE",sym_end,bench_end

def price_input_hash(symbol_hist,benchmark_hist,as_of):
    # Hash all <= as_of rows loaded for these two instruments. This freezes the
    # exact read-only price_history evidence used by the prospective snapshot.
    obj={
        "symbol_history":[x for x in symbol_hist if x[0]<=as_of],
        "benchmark_history":[x for x in benchmark_hist if x[0]<=as_of],
    }
    return semantic_hash(obj)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--snapshot-authority-json",default="reports/m77_20_3_prospective_sector_membership_benchmark_snapshot_capture_authority.json")
    ap.add_argument("--snapshot-json",default=None)
    ap.add_argument("--output-root",default="research_data/m77_20_4/prospective_f071_shadow")
    ap.add_argument("--output-json",default="reports/m77_20_4_prospective_f071_feature_materialization_immutable_shadow_capture_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_20_4_f071_coverage_summary.csv")
    a=ap.parse_args()
    root=Path(a.project_root).resolve()

    apath=R(root,a.snapshot_authority_json)
    if not apath.exists():
        raise F071Error(f"M77.20.3 authority missing: {apath}")
    authority=J(apath)
    if authority.get("status")!="READY":
        raise F071Error("M77.20.3 snapshot authority invalid")
    if authority.get("snapshot_immutability_certified") is not True:
        raise F071Error("M77.20.3 snapshot immutability not certified")
    if authority.get("prospective_membership_snapshot_capture_certified") is not True:
        raise F071Error("membership capture not certified")
    if authority.get("prospective_benchmark_snapshot_capture_certified") is not True:
        raise F071Error("benchmark capture not certified")
    if authority.get("prospective_outcomes_opened") is not False:
        raise F071Error("prospective outcomes already opened")
    if authority.get("prospective_F071_materialized") is not False:
        raise F071Error("upstream authority unexpectedly says F071 materialized")

    snapshot_date=str(authority["snapshot_date"])[:10]
    if snapshot_date<EARLIEST_AUTHORIZED_DATE:
        raise F071Error("snapshot date precedes authorized Cycle 2 start")

    if a.snapshot_json:
        spath=R(root,a.snapshot_json)
    else:
        spath=R(root,authority["snapshot_file"])
    if not spath.exists():
        raise F071Error(f"immutable sector snapshot missing: {spath}")
    snapshot=J(spath)
    if snapshot.get("snapshot_date")!=snapshot_date:
        raise F071Error("snapshot date authority/file mismatch")
    if snapshot.get("snapshot_semantic_sha256")!=authority.get("snapshot_semantic_sha256"):
        raise F071Error("snapshot semantic hash authority/file mismatch")
    gov=snapshot.get("governance") or {}
    if gov.get("outcomes_read") is not False or gov.get("F071_materialized") is not False:
        raise F071Error("sector snapshot governance boundary violated")
    if gov.get("unmapped_sector_policy")!="EXPLICIT_MISSING_F071_NO_INFERENCE":
        raise F071Error("unmapped-sector policy changed")
    if gov.get("benchmark_fallback_to_SPY_authorized") is not False:
        raise F071Error("SPY fallback unexpectedly authorized")

    memberships=snapshot.get("membership_records") or []
    benchmarks={x["sector"]:x for x in snapshot.get("benchmark_records") or []}
    if len(memberships)!=authority.get("membership_count"):
        raise F071Error("membership cardinality changed")

    required_symbols=sorted({
        str(m["symbol"]).upper()
        for m in memberships
    } | {
        str(b["benchmark_symbol"]).upper()
        for b in benchmarks.values()
        if b.get("benchmark_status")=="AVAILABLE" and b.get("benchmark_symbol")
    })

    # Production underlying history is read-only for this research step.
    with SessionLocal() as session:
        rows=session.execute(
            text("""
                SELECT symbol,date,close
                FROM price_history
                WHERE UPPER(symbol) = ANY(:symbols)
                  AND date <= :as_of
                ORDER BY symbol,date
            """),
            {"symbols":required_symbols,"as_of":date.fromisoformat(snapshot_date)},
        ).mappings().all()

    histories=normalize_hist(rows)
    records=[]
    reasons=Counter()
    present_components=Counter()
    endpoint_dates=Counter()

    for m in memberships:
        symbol=str(m["symbol"]).upper()
        sector=m["sector"]
        b=benchmarks.get(sector)
        base={
            "symbol":symbol,
            "sector":sector,
            "snapshot_date":snapshot_date,
            "membership_snapshot_semantic_sha256":snapshot["snapshot_semantic_sha256"],
            "membership_source_identity":m.get("source_identity"),
            "membership_source_as_of_date":m.get("source_as_of_date"),
        }

        if not b or b.get("benchmark_status")!="AVAILABLE" or not b.get("benchmark_symbol"):
            rec={**base,
                 "benchmark_symbol":None if not b else b.get("benchmark_symbol"),
                 "F071":{"rs_sector_13w":None,"rs_sector_26w":None},
                 "component_status":{"rs_sector_13w":"MISSING_NO_GOVERNED_BENCHMARK","rs_sector_26w":"MISSING_NO_GOVERNED_BENCHMARK"},
                 "F071_missing":True,
                 "F071_missing_reason":"MISSING_NO_GOVERNED_BENCHMARK",
                 "price_input_semantic_sha256":None}
            reasons["MISSING_NO_GOVERNED_BENCHMARK"]+=1
            records.append(rec)
            continue

        bench=str(b["benchmark_symbol"]).upper()
        sh=histories.get(symbol) or []
        bh=histories.get(bench) or []
        if not sh or not bh:
            rec={**base,"benchmark_symbol":bench,
                 "F071":{"rs_sector_13w":None,"rs_sector_26w":None},
                 "component_status":{"rs_sector_13w":"MISSING_PRICE_HISTORY","rs_sector_26w":"MISSING_PRICE_HISTORY"},
                 "F071_missing":True,"F071_missing_reason":"MISSING_PRICE_HISTORY",
                 "price_input_semantic_sha256":None}
            reasons["MISSING_PRICE_HISTORY"]+=1
            records.append(rec)
            continue

        r13,s13,se13,be13=component(sh,bh,snapshot_date,65)
        r26,s26,se26,be26=component(sh,bh,snapshot_date,130)
        for name,val,status in (("rs_sector_13w",r13,s13),("rs_sector_26w",r26,s26)):
            if val is not None:
                present_components[name]+=1
            else:
                reasons[status]+=1
        if se13:
            endpoint_dates[se13]+=1
        if se26:
            endpoint_dates[se26]+=1

        missing=(r13 is None and r26 is None)
        reason=None
        if missing:
            reason=";".join(sorted({s13,s26}))
        rec={**base,
             "benchmark_symbol":bench,
             "F071":{"rs_sector_13w":r13,"rs_sector_26w":r26},
             "component_status":{"rs_sector_13w":s13,"rs_sector_26w":s26},
             "component_endpoint_session":{
                 "rs_sector_13w":{"symbol":se13,"benchmark":be13},
                 "rs_sector_26w":{"symbol":se26,"benchmark":be26},
             },
             "F071_missing":missing,
             "F071_missing_reason":reason,
             "price_input_semantic_sha256":price_input_hash(sh,bh,snapshot_date)}
        records.append(rec)

    records.sort(key=lambda x:x["symbol"])
    materialized=sum(1 for x in records if not x["F071_missing"])
    missing=len(records)-materialized
    full_coverage=sum(1 for x in records if x["F071"]["rs_sector_13w"] is not None and x["F071"]["rs_sector_26w"] is not None)
    partial_coverage=materialized-full_coverage

    payload={
      "version":VERSION,
      "snapshot_date":snapshot_date,
      "sector_snapshot_semantic_sha256":snapshot["snapshot_semantic_sha256"],
      "price_source":"POSTGRESQL_PRICE_HISTORY_READ_ONLY",
      "formula":{
        "rs_sector_13w":"symbol trailing 65 available sessions return minus captured sector benchmark trailing 65 available sessions return",
        "rs_sector_26w":"symbol trailing 130 available sessions return minus captured sector benchmark trailing 130 available sessions return",
        "same_as_of_or_prior_only":True,
        "symbol_benchmark_endpoint_session_must_match":True,
      },
      "records":records,
      "governance":{
        "prospective_only":True,
        "outcomes_read":False,
        "future_bars_used":False,
        "benchmark_fallback_to_SPY_performed":False,
        "cross_sector_imputation_performed":False,
        "historical_F071_backfill_performed":False,
        "consumed_final_holdout_opened":False,
        "production_authority_effect":False,
      }
    }
    fhash=semantic_hash(payload)
    payload["feature_snapshot_semantic_sha256"]=fhash

    outroot=R(root,a.output_root)
    outpath=outroot/snapshot_date/"f071_shadow_feature_snapshot.json"
    if outpath.exists():
        old=J(outpath)
        if old.get("feature_snapshot_semantic_sha256")!=fhash:
            raise F071Error(
                f"IMMUTABILITY_VIOLATION_EXISTING_F071_SNAPSHOT_DIFFERS date={snapshot_date}"
            )
        mode="IDEMPOTENT_EXISTING_F071_SNAPSHOT_REUSED"
        payload=old
    else:
        atomic(outpath,json.dumps(payload,indent=2,sort_keys=True).encode("utf-8")+b"\n")
        mode="NEW_IMMUTABLE_F071_SHADOW_SNAPSHOT_CAPTURED"

    manifest_path=outroot/"manifest.json"
    manifest={"version":"M77.20.4-PROSPECTIVE-F071-SHADOW-MANIFEST-1.0","snapshots":[]}
    if manifest_path.exists():
        manifest=J(manifest_path)
    entries={x["snapshot_date"]:x for x in manifest.get("snapshots") or []}
    ent={"snapshot_date":snapshot_date,
         "snapshot_file":str(outpath.relative_to(root)),
         "feature_snapshot_semantic_sha256":payload["feature_snapshot_semantic_sha256"],
         "observation_count":len(records),
         "materialized_observation_count":materialized,
         "missing_observation_count":missing}
    if snapshot_date in entries and entries[snapshot_date]!=ent:
        raise F071Error("manifest immutability violation")
    entries[snapshot_date]=ent
    manifest["snapshots"]=[entries[k] for k in sorted(entries)]
    manifest["latest_snapshot_date"]=max(entries)
    atomic(manifest_path,json.dumps(manifest,indent=2,sort_keys=True).encode("utf-8")+b"\n")

    report={
      "version":VERSION,
      "status":"READY",
      "execution_mode":mode,
      "snapshot_date":snapshot_date,
      "sector_snapshot_semantic_sha256":snapshot["snapshot_semantic_sha256"],
      "feature_snapshot_semantic_sha256":payload["feature_snapshot_semantic_sha256"],
      "price_source":"POSTGRESQL_PRICE_HISTORY_READ_ONLY",
      "observation_count":len(records),
      "F071_materialized_observation_count":materialized,
      "F071_missing_observation_count":missing,
      "F071_full_13w_26w_coverage_count":full_coverage,
      "F071_partial_coverage_count":partial_coverage,
      "rs_sector_13w_present_count":present_components["rs_sector_13w"],
      "rs_sector_26w_present_count":present_components["rs_sector_26w"],
      "missing_reason_counts":dict(sorted(reasons.items())),
      "effective_endpoint_session_counts":dict(sorted(endpoint_dates.items())),
      "formula_semantics_frozen":True,
      "same_as_of_or_prior_only":True,
      "endpoint_session_match_required":True,
      "feature_snapshot_immutability_certified":True,
      "different_content_same_date_rewrite_authorized":False,
      "benchmark_fallback_to_SPY_performed":False,
      "cross_sector_imputation_performed":False,
      "historical_F071_backfill_performed":False,
      "consumed_final_holdout_opened":False,
      "prospective_F071_materialized":True,
      "prospective_outcomes_opened":False,
      "prospective_scoring_performed":False,
      "production_authority_effect":False,
      "feature_snapshot_file":str(outpath.relative_to(root)),
      "manifest_file":str(manifest_path.relative_to(root)),
      "next_step":"BUILD_M77_20_5_PROSPECTIVE_BASELINE_FEATURE_SHADOW_CAPTURE_AND_PAIRED_OBSERVATION_AUTHORITY",
    }

    oj=R(root,a.output_json)
    oc=R(root,a.output_csv)
    oj.parent.mkdir(parents=True,exist_ok=True)
    atomic(oj,json.dumps(report,indent=2,sort_keys=True).encode("utf-8")+b"\n")
    with oc.open("w",encoding="utf-8",newline="") as f:
        import csv
        fields=[
          "snapshot_date","observation_count","F071_materialized_observation_count",
          "F071_missing_observation_count","F071_full_13w_26w_coverage_count",
          "F071_partial_coverage_count","rs_sector_13w_present_count",
          "rs_sector_26w_present_count","feature_snapshot_semantic_sha256","execution_mode"
        ]
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerow({k:report[k] for k in fields})

    print("=== M77.20.4 PROSPECTIVE F071 FEATURE MATERIALIZATION & IMMUTABLE SHADOW CAPTURE AUTHORITY ===")
    print("status: READY")
    print("execution_mode:",mode)
    print("snapshot_date:",snapshot_date)
    print("price_source: POSTGRESQL_PRICE_HISTORY_READ_ONLY")
    print("observation_count:",len(records))
    print("F071_materialized_observation_count:",materialized)
    print("F071_missing_observation_count:",missing)
    print("F071_full_13w_26w_coverage_count:",full_coverage)
    print("F071_partial_coverage_count:",partial_coverage)
    print("rs_sector_13w_present_count:",present_components["rs_sector_13w"])
    print("rs_sector_26w_present_count:",present_components["rs_sector_26w"])
    print("missing_reason_counts:",dict(sorted(reasons.items())))
    print("effective_endpoint_session_counts:",dict(sorted(endpoint_dates.items())))
    print("formula_semantics_frozen: True")
    print("same_as_of_or_prior_only: True")
    print("endpoint_session_match_required: True")
    print("feature_snapshot_immutability_certified: True")
    print("benchmark_fallback_to_SPY_performed: False")
    print("cross_sector_imputation_performed: False")
    print("historical_F071_backfill_performed: False")
    print("consumed_final_holdout_opened: False")
    print("prospective_F071_materialized: True")
    print("prospective_outcomes_opened: False")
    print("prospective_scoring_performed: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",oj)
    print("csv:",oc)
    print("feature_snapshot:",outpath)
    print("manifest:",manifest_path)

if __name__=="__main__":
    main()
