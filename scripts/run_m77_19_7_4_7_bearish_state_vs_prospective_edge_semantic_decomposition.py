#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, math, statistics, tempfile, os, hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

VERSION="M77.19.7.4.7-BEARISH-STATE-VS-PROSPECTIVE-EDGE-SEMANTIC-DECOMPOSITION-1.0"
EXPECTED_REPLAY_SHA="0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
EXPECTED_SYMBOLS=602
FIXED_HORIZONS=(5,10,20)
MIN_CELL_COUNT=500

class EvidenceError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    p=Path(raw)
    if p.exists(): return p
    q=root/p
    if q.exists(): return q
    return p

def parse_bool(v:Any)->bool:
    if isinstance(v,bool):return v
    return str(v).strip().lower() in ("true","1","yes")

def f(v:Any)->float|None:
    if v in (None,"","None","null"):return None
    x=float(v)
    return x if math.isfinite(x) else None

def stats(xs:list[float])->dict[str,Any]:
    if not xs:return {"count":0,"accuracy":None,"mean":None,"median":None}
    ys=sorted(xs)
    return {
        "count":len(xs),
        "accuracy":sum(x>0 for x in xs)/len(xs),
        "mean":statistics.fmean(xs),
        "median":statistics.median(xs),
        "p25":ys[int(.25*(len(ys)-1))],
        "p75":ys[int(.75*(len(ys)-1))],
    }

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--lifecycle-authority-json",default="reports/m77_19_7_4_6_bearish_lifecycle_exhaustion_vs_continuation_causal_forensics.json")
    ap.add_argument("--lifecycle-csv",default="reports/m77_19_7_4_6_bearish_lifecycle_observation_evidence.csv")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_7_bearish_state_vs_prospective_edge_semantic_decomposition.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_7_prospective_edge_cells.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    rp=resolve(root,args.replay_authority_json);op=resolve(root,args.outcome_authority_json)
    lp=resolve(root,args.lifecycle_authority_json);lc=resolve(root,args.lifecycle_csv)

    if sha256_file(rp)!=EXPECTED_REPLAY_SHA: raise EvidenceError("replay authority SHA mismatch")
    if sha256_file(op)!=EXPECTED_OUTCOME_SHA: raise EvidenceError("outcome authority SHA mismatch")
    life=load_json(lp)
    if life.get("status")!="READY": raise EvidenceError("M77.19.7.4.6 lifecycle authority not READY")
    if life.get("successful_symbol_count")!=EXPECTED_SYMBOLS: raise EvidenceError("lifecycle symbol count mismatch")
    if not lc.is_file(): raise EvidenceError("lifecycle CSV missing")

    cells=defaultdict(list)
    rows=0
    with lc.open("r",encoding="utf-8",newline="") as fh:
        r=csv.DictReader(fh)
        required={"horizon_sessions","native_direction","lifecycle_state","realized_bearish_directional_return",
                  "overlay_BREAKDOWN_CONFIRMED","overlay_CAPITULATION","overlay_PRIOR_20_DECLINE_GE_10PCT",
                  "overlay_DRAWDOWN_63_GE_15PCT","overlay_STRONG_BEARISH_ALIGNMENT_2PLUS"}
        if not required.issubset(set(r.fieldnames or [])):
            raise EvidenceError(f"lifecycle CSV missing fields {sorted(required-set(r.fieldnames or []))}")
        for row in r:
            h=int(row["horizon_sessions"])
            if h not in FIXED_HORIZONS: continue
            y=float(row["realized_bearish_directional_return"])
            life_state=row["lifecycle_state"]
            native=row["native_direction"]
            flags={
                "BREAKDOWN_CONFIRMED":parse_bool(row["overlay_BREAKDOWN_CONFIRMED"]),
                "CAPITULATION":parse_bool(row["overlay_CAPITULATION"]),
                "PRIOR_20_DECLINE_GE_10PCT":parse_bool(row["overlay_PRIOR_20_DECLINE_GE_10PCT"]),
                "DRAWDOWN_63_GE_15PCT":parse_bool(row["overlay_DRAWDOWN_63_GE_15PCT"]),
                "STRONG_BEARISH_ALIGNMENT_2PLUS":parse_bool(row["overlay_STRONG_BEARISH_ALIGNMENT_2PLUS"]),
            }
            rows+=1
            # descriptive-state cells
            cells[("LIFECYCLE",life_state,h)].append(y)
            cells[("NATIVE_CLASS",native,h)].append(y)
            # prospective-edge decomposition cells
            for k,v in flags.items():
                cells[(f"OVERLAY::{k}",f"{life_state}::{v}",h)].append(y)
            # predeclared compound cells
            late = life_state=="PERSISTENT_LATE"
            early = life_state=="EARLY_TRANSITION"
            cells[("EDGE_COMPOUND","EARLY_CLEAN",h)].append(y) if early and not any(flags.values()) else None
            cells[("EDGE_COMPOUND","LATE_EXHAUSTION",h)].append(y) if late and (
                flags["BREAKDOWN_CONFIRMED"] or flags["CAPITULATION"] or
                flags["PRIOR_20_DECLINE_GE_10PCT"] or flags["DRAWDOWN_63_GE_15PCT"]
            ) else None
            cells[("EDGE_COMPOUND","LATE_STRONG_ALIGNMENT",h)].append(y) if late and flags["STRONG_BEARISH_ALIGNMENT_2PLUS"] else None
            cells[("EDGE_COMPOUND","ESTABLISHED_WITHOUT_EXHAUSTION",h)].append(y) if life_state=="ESTABLISHED" and not (
                flags["BREAKDOWN_CONFIRMED"] or flags["CAPITULATION"]
            ) else None

    out_rows=[]
    for (family,state,h),xs in sorted(cells.items()):
        s=stats(xs)
        s.update({"family":family,"state":state,"horizon_sessions":h,"eligible_for_interpretation":s["count"]>=MIN_CELL_COUNT})
        out_rows.append(s)

    # Comparative decision table against lifecycle baseline at same horizon.
    baseline={(r["state"],r["horizon_sessions"]):r for r in out_rows if r["family"]=="LIFECYCLE"}
    comparisons=[]
    for r in out_rows:
        if r["family"]!="EDGE_COMPOUND":continue
        # Map compounds to primary lifecycle comparator.
        comparator={
            "EARLY_CLEAN":"EARLY_TRANSITION",
            "LATE_EXHAUSTION":"PERSISTENT_LATE",
            "LATE_STRONG_ALIGNMENT":"PERSISTENT_LATE",
            "ESTABLISHED_WITHOUT_EXHAUSTION":"ESTABLISHED",
        }[r["state"]]
        b=baseline[(comparator,r["horizon_sessions"])]
        comparisons.append({
            "state":r["state"],"horizon_sessions":r["horizon_sessions"],
            "count":r["count"],"accuracy":r["accuracy"],"median":r["median"],
            "baseline_lifecycle":comparator,
            "baseline_accuracy":b["accuracy"],"baseline_median":b["median"],
            "accuracy_delta":None if r["accuracy"] is None else r["accuracy"]-b["accuracy"],
            "median_delta":None if r["median"] is None else r["median"]-b["median"],
            "eligible_for_interpretation":r["eligible_for_interpretation"],
        })

    report={
        "version":VERSION,"status":"READY","successful_symbol_count":EXPECTED_SYMBOLS,
        "replay_authority_sha256":EXPECTED_REPLAY_SHA,"outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "lifecycle_authority_sha256":sha256_file(lp),"lifecycle_csv_sha256":sha256_file(lc),
        "fixed_horizons_sessions":list(FIXED_HORIZONS),"minimum_cell_count":MIN_CELL_COUNT,
        "observation_horizon_row_count":rows,
        "prospective_edge_cells":out_rows,
        "compound_vs_lifecycle_comparisons":comparisons,
        "semantic_decomposition":{
            "descriptive_bearish_state":"native direction/lifecycle state describes current historical condition",
            "prospective_bearish_edge":"forward downside evidence conditional on lifecycle/exhaustion context",
            "production_mapping_authorized":False,
        },
        "governance":{
            "threshold_search_or_optimization":False,"parameter_fitting":False,"classifier_training":False,
            "future_feature_leakage":False,"automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,"production_authority_effect":False,
            "database_access":"NONE","polygon_api_queried":False,"price_history_table_used":False,
        },
        "next_step":"REVIEW_M77_19_7_4_7_SEMANTIC_DECOMPOSITION_BEFORE_ANY_CHAMPION_CANDIDATE",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=["family","state","horizon_sessions","count","accuracy","mean","median","p25","p75","eligible_for_interpretation"]
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(out_rows)

    print("=== M77.19.7.4.7 BEARISH STATE VS PROSPECTIVE EDGE SEMANTIC DECOMPOSITION ===")
    print("status: READY")
    print(f"successful_symbol_count: {EXPECTED_SYMBOLS}")
    print(f"observation_horizon_row_count: {rows}")
    for h in FIXED_HORIZONS:
        for state in ("EARLY_CLEAN","ESTABLISHED_WITHOUT_EXHAUSTION","LATE_EXHAUSTION","LATE_STRONG_ALIGNMENT"):
            r=next((x for x in comparisons if x["horizon_sessions"]==h and x["state"]==state),None)
            if r:
                print(f"horizon_{h}_{state}: count={r['count']} accuracy={r['accuracy']} median={r['median']} "
                      f"baseline={r['baseline_lifecycle']} accuracy_delta={r['accuracy_delta']} median_delta={r['median_delta']}")
    print("threshold_search_or_optimization: False")
    print("parameter_fitting: False")
    print("automatic_bearish_signal_inversion: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_7_SEMANTIC_DECOMPOSITION_BEFORE_ANY_CHAMPION_CANDIDATE")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
