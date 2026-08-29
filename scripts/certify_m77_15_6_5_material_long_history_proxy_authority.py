#!/usr/bin/env python3
from __future__ import annotations

import csv,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_15_6_5_material_long_history_proxy_certification.json"
OUT=ROOT/"reports/m77/m77_15_6_5_material_long_history_proxy_authority_certification.json"

VERSION="M77.15.6.5-MATERIAL-LONG-HISTORY-PROXY-AUTHORITY-CERTIFICATION-1.0"

def write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def load_csv(path):
    with path.open() as f:
        return list(csv.DictReader(f))

def row_dates(rows):
    return [r["date"] for r in rows]

def ohlc_violations(rows):
    bad=[]
    for r in rows:
        try:
            o=float(r["open"]); h=float(r["high"]); l=float(r["low"]); c=float(r["close"])
        except Exception:
            bad.append({"date":r.get("date"),"reason":"MISSING_OR_INVALID_OHLC"})
            continue
        if min(o,h,l,c)<=0:
            bad.append({"date":r["date"],"reason":"NONPOSITIVE_OHLC"})
        elif h < max(o,c,l) or l > min(o,c,h):
            bad.append({"date":r["date"],"reason":"OHLC_INVARIANT"})
    return bad

def duplicates(rows):
    seen=set(); dup=[]
    for d in row_dates(rows):
        if d in seen and d not in dup:
            dup.append(d)
        seen.add(d)
    return dup

def main():
    cfg=json.loads(CFG.read_text())
    manifest_path=ROOT/cfg["source_manifest"]
    if not manifest_path.exists():
        raise SystemExit("M77.15.6.4 manifest missing; run M77.15.6.4 diagnostic first")
    m=json.loads(manifest_path.read_text())

    source=m["source_series"]
    qline=m["qqq_lineage"]

    spy_path=Path(source["SPY"]["normalized_path"])
    qqq_lineage_path=Path(qline["stitched_path"])
    iwm_path=Path(source["IWM"]["normalized_path"])
    for p in (spy_path,qqq_lineage_path,iwm_path):
        if not p.exists():
            raise SystemExit(f"required normalized authority missing: {p}")

    series={
        "SPX":load_csv(spy_path),
        "NDX":load_csv(qqq_lineage_path),
        "RUT":load_csv(iwm_path),
    }

    sets={k:set(row_dates(v)) for k,v in series.items()}
    common=sorted(set.intersection(*sets.values()))
    common_start=common[0] if common else None
    common_end=common[-1] if common else None

    target_gates={}
    for target,rows in series.items():
        dups=duplicates(rows)
        bad=ohlc_violations(rows)
        target_gates[target]={
            "research_instrument":cfg["targets"][target]["research_instrument"],
            "row_count":len(rows),
            "first_date":row_dates(rows)[0] if rows else None,
            "last_date":row_dates(rows)[-1] if rows else None,
            "duplicate_dates_zero":len(dups)==0,
            "duplicate_date_count":len(dups),
            "ohlc_violations_zero":len(bad)==0,
            "ohlc_violation_count":len(bad),
        }

    # QQQ lineage source-ticker contract.
    qrows=series["NDX"]
    qqq_lineage_source_gate=True
    qqq_lineage_violations=[]
    for r in qrows:
        d=r["date"]; src=r["polygon_ticker"]
        expected="QQQ" if d <= "2004-11-30" or d >= "2011-03-23" else "QQQQ"
        if src!=expected:
            qqq_lineage_source_gate=False
            qqq_lineage_violations.append({"date":d,"source_ticker":src,"expected":expected})

    raw_provenance_ok=True
    missing_provenance=[]
    for sym in ("SPY","QQQ","QQQQ","IWM"):
        s=source[sym]
        for page in s.get("raw_pages") or []:
            if not page.get("raw_sha256") or not page.get("raw_path"):
                raw_provenance_ok=False
                missing_provenance.append({"symbol":sym,"page":page})

    gates={
        "common_session_intersection_present":bool(common),
        "common_start_matches_frozen_gate":common_start==cfg["certified_common_start"],
        "common_session_count_ge_minimum":len(common)>=int(cfg["minimum_common_sessions"]),
        "all_targets_zero_duplicates":all(v["duplicate_dates_zero"] for v in target_gates.values()),
        "all_targets_zero_ohlc_violations":all(v["ohlc_violations_zero"] for v in target_gates.values()),
        "qqq_lineage_source_ticker_contract":qqq_lineage_source_gate,
        "source_provenance_checksums_present":raw_provenance_ok,
        "canonical_authority_not_overwritten":m["governance"]["canonical_authorities_mutated"] is False,
    }

    certified=all(gates.values())

    out={
        "version":VERSION,
        "status":"READY",
        "authority_type":"MATERIAL_LONG_HISTORY_TRADABLE_PROXY",
        "source_manifest":str(manifest_path),
        "common_authority":{
            "common_start":common_start,
            "common_end":common_end,
            "common_session_count":len(common),
            "minimum_common_sessions":cfg["minimum_common_sessions"],
            "frozen_start_gate":cfg["certified_common_start"],
        },
        "targets":target_gates,
        "qqq_lineage":{
            "source_ticker_contract_pass":qqq_lineage_source_gate,
            "violation_count":len(qqq_lineage_violations),
            "violations_sample":qqq_lineage_violations[:20],
        },
        "source_provenance":{
            "checksums_present":raw_provenance_ok,
            "missing_sample":missing_provenance[:20],
        },
        "gates":gates,
        "certified_for_m77_15_7_long_history_replication":certified,
        "promotion_governance":{
            "proxy_results_are_not_index_results":True,
            "proxy_only_survivor_may_not_advance":True,
            "canonical_recent_index_confirmation_required":True,
            "same_effect_direction_required_across_authorities":True,
            "dependence_robust_confirmation_required_after_cross_authority_survival":True,
        },
        "replication_era_policy":{
            "frozen_eras":[
                ["2003-09-10","2008-12-31"],
                ["2009-01-01","2014-12-31"],
                ["2015-01-01","2020-12-31"],
                ["2021-01-01",common_end],
            ],
            "posthoc_era_changes_prohibited":True,
        },
        "database_writes":False,
        "production_price_history_writes":False,
        "production_authority_effect":False,
        "next_step":"BUILD_M77_15_7_LONG_HISTORY_REPLICATION" if certified else "REVIEW_M77_15_6_5_CERTIFICATION_FAILURES"
    }
    write_json_atomic(OUT,out)
    print(json.dumps(out,indent=2))

if __name__=="__main__":
    main()
