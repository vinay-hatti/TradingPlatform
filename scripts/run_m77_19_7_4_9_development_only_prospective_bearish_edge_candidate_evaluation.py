#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math, os, statistics, tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.7.4.9-DEVELOPMENT-ONLY-PROSPECTIVE-BEARISH-EDGE-CANDIDATE-EVALUATION-1.0"
EXPECTED_REPLAY_SHA="0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
EXPECTED_HOLDOUT_VERSION="M77.19.7.4.8-PROSPECTIVE-BEARISH-EDGE-HYPOTHESIS-REGISTRY-TEMPORAL-HOLDOUT-AUTHORITY-1.0"
EXPECTED_SYMBOLS=602
FIXED_HORIZONS=(5,10,20)
DEVELOPMENT_END="2017-12-31"

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
    if not p.is_absolute():
        q=root/p
        if q.exists(): return q
    return p

def iter_jsonl(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip(): continue
            try: yield json.loads(line)
            except Exception as exc: raise EvidenceError(f"{path}:{i}: invalid json") from exc

def get_path(obj:Any,path:str)->Any:
    cur=obj
    for p in path.split("."):
        if not isinstance(cur,dict) or p not in cur:return None
        cur=cur[p]
    return cur

def stats(xs:list[float])->dict[str,Any]:
    if not xs:return {"count":0,"accuracy":None,"mean":None,"median":None}
    ys=sorted(xs)
    return {
        "count":len(xs),
        "accuracy":sum(x>0 for x in xs)/len(xs),
        "mean":statistics.fmean(xs),
        "median":statistics.median(xs),
        "p25":ys[int(.25*(len(ys)-1))],
        "p75":ys[int(.75*(len(ys)-1))]
    }

def is_dev(as_of:str)->bool:
    return as_of[:10] <= DEVELOPMENT_END

def lifecycle_from_streak(streak:int)->str:
    if streak<=2:return "EARLY_TRANSITION"
    if streak<=8:return "ESTABLISHED"
    return "PERSISTENT_LATE"

def candidate_h1(row:Mapping[str,Any])->bool:
    return (
        str(row.get("native_direction","")).upper() in ("BEARISH","STRONG_BEARISH")
        and str(row.get("transitioned_into_bearish","")).lower() in ("true","1")
        and not parse_bool(row.get("overlay_PRIOR_20_DECLINE_GE_10PCT"))
        and not parse_bool(row.get("overlay_DRAWDOWN_63_GE_15PCT"))
    )

def candidate_h2(row:Mapping[str,Any])->bool:
    return (
        str(row.get("native_direction","")).upper() in ("BEARISH","STRONG_BEARISH")
        and str(row.get("breakout_state","")).upper()=="BREAKDOWN_SETUP"
        and int(float(row.get("bearish_streak_observations") or 0))<=2
    )

def candidate_h3(row:Mapping[str,Any])->bool:
    return (
        str(row.get("native_direction","")).upper() in ("BEARISH","STRONG_BEARISH")
        and not parse_bool(row.get("overlay_CAPITULATION"))
        and not parse_bool(row.get("overlay_BREAKDOWN_CONFIRMED"))
        and not parse_bool(row.get("overlay_PRIOR_20_DECLINE_GE_10PCT"))
        and not parse_bool(row.get("overlay_DRAWDOWN_63_GE_15PCT"))
        and lifecycle_from_streak(int(float(row.get("bearish_streak_observations") or 0)))!="PERSISTENT_LATE"
    )

def parse_bool(v:Any)->bool:
    if isinstance(v,bool):return v
    return str(v).strip().lower() in ("true","1","yes")

def candidate_h4(row:Mapping[str,Any])->bool:
    # H4 cannot be faithfully evaluated from the lifecycle CSV because exact
    # structural-room geometry was not materialized there. It remains
    # REGISTERED_BUT_NOT_EVALUABLE in 7.4.9 rather than being guessed.
    return False

CANDIDATES={
    "H1_FRESH_DOWNSIDE_TRANSITION":candidate_h1,
    "H2_BREAKDOWN_INITIATION":candidate_h2,
    "H3_CONTINUATION_WITHOUT_EXHAUSTION":candidate_h3,
    "H4_REMAINING_STRUCTURAL_DOWNSIDE_ROOM":candidate_h4,
}

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent); os.close(fd)
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
    ap.add_argument("--holdout-authority-json",default="reports/m77_19_7_4_8_prospective_bearish_edge_hypothesis_registry_temporal_holdout_authority.json")
    ap.add_argument("--lifecycle-csv",default="reports/m77_19_7_4_6_bearish_lifecycle_observation_evidence.csv")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_9_development_only_prospective_bearish_edge_candidate_evaluation.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_9_development_candidate_evidence.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    rp=resolve(root,args.replay_authority_json);op=resolve(root,args.outcome_authority_json)
    hp=resolve(root,args.holdout_authority_json);lc=resolve(root,args.lifecycle_csv)

    if sha256_file(rp)!=EXPECTED_REPLAY_SHA:raise EvidenceError("replay SHA mismatch")
    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:raise EvidenceError("outcome SHA mismatch")
    holdout=load_json(hp)
    if holdout.get("version")!=EXPECTED_HOLDOUT_VERSION or holdout.get("status")!="READY":
        raise EvidenceError("holdout authority invalid")
    if holdout.get("successful_symbol_count")!=EXPECTED_SYMBOLS:raise EvidenceError("holdout symbol count mismatch")

    buckets=defaultdict(lambda:defaultdict(list))
    baseline=defaultdict(list)
    total_dev_rows=0
    seen_nondev=False

    with lc.open("r",encoding="utf-8",newline="") as fh:
        r=csv.DictReader(fh)
        for row in r:
            as_of=row["as_of"][:10]
            if not is_dev(as_of):
                seen_nondev=True
                continue
            total_dev_rows+=1
            h=int(row["horizon_sessions"])
            if h not in FIXED_HORIZONS:continue
            y=float(row["realized_bearish_directional_return"])
            baseline[h].append(y)
            for cid,fn in CANDIDATES.items():
                if cid=="H4_REMAINING_STRUCTURAL_DOWNSIDE_ROOM":
                    continue
                if fn(row):
                    buckets[cid][h].append(y)

    evidence=[]
    for cid in CANDIDATES:
        status="EVALUATED" if cid!="H4_REMAINING_STRUCTURAL_DOWNSIDE_ROOM" else "REGISTERED_BUT_NOT_EVALUABLE_FROM_7_4_6_EVIDENCE"
        for h in FIXED_HORIZONS:
            s=stats(buckets[cid][h]) if status=="EVALUATED" else {"count":0,"accuracy":None,"mean":None,"median":None,"p25":None,"p75":None}
            b=stats(baseline[h])
            evidence.append({
                "candidate_id":cid,"horizon_sessions":h,"status":status,
                **s,
                "baseline_accuracy":b["accuracy"],"baseline_median":b["median"],
                "accuracy_delta_vs_all_bearish_dev":None if s["accuracy"] is None else s["accuracy"]-b["accuracy"],
                "median_delta_vs_all_bearish_dev":None if s["median"] is None else s["median"]-b["median"],
            })

    report={
        "version":VERSION,"status":"READY",
        "replay_authority_sha256":EXPECTED_REPLAY_SHA,"outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "holdout_authority_sha256":sha256_file(hp),"lifecycle_csv_sha256":sha256_file(lc),
        "development_end":DEVELOPMENT_END,"development_observation_horizon_row_count":total_dev_rows,
        "nondevelopment_rows_seen_and_skipped":seen_nondev,
        "candidate_evidence":evidence,
        "candidate_status":{
            "H1_FRESH_DOWNSIDE_TRANSITION":"EVALUATED",
            "H2_BREAKDOWN_INITIATION":"EVALUATED",
            "H3_CONTINUATION_WITHOUT_EXHAUSTION":"EVALUATED",
            "H4_REMAINING_STRUCTURAL_DOWNSIDE_ROOM":"REGISTERED_BUT_NOT_EVALUABLE_FROM_7_4_6_EVIDENCE",
        },
        "evaluation_scope":{
            "development_partition_only":True,
            "validation_outcomes_used_for_candidate_scoring":False,
            "final_holdout_outcomes_used_for_candidate_scoring":False,
            "validation_candidate_accept_reject_performed":False,
            "final_holdout_opened":False,
            "champion_selected":False,
        },
        "governance":{
            "threshold_search_or_optimization":False,"parameter_fitting":False,"calibrator_fitting":False,
            "classifier_training":False,"automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,"production_authority_effect":False,
        },
        "next_step":"REVIEW_M77_19_7_4_9_DEVELOPMENT_EVIDENCE_AND_MATERIALIZE_H4_STRUCTURAL_ROOM_IF_REQUIRED",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(evidence[0].keys())
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(evidence)

    print("=== M77.19.7.4.9 DEVELOPMENT-ONLY PROSPECTIVE BEARISH EDGE CANDIDATE EVALUATION ===")
    print("status: READY")
    print(f"development_observation_horizon_row_count: {total_dev_rows}")
    print(f"nondevelopment_rows_seen_and_skipped: {seen_nondev}")
    for cid in CANDIDATES:
        for h in FIXED_HORIZONS:
            e=next(x for x in evidence if x["candidate_id"]==cid and x["horizon_sessions"]==h)
            print(f"{cid}_h{h}: status={e['status']} count={e['count']} accuracy={e['accuracy']} median={e['median']} "
                  f"accuracy_delta={e['accuracy_delta_vs_all_bearish_dev']} median_delta={e['median_delta_vs_all_bearish_dev']}")
    print("validation_outcomes_used_for_candidate_scoring: False")
    print("final_holdout_outcomes_used_for_candidate_scoring: False")
    print("champion_selected: False")
    print("threshold_search_or_optimization: False")
    print("parameter_fitting: False")
    print("automatic_bearish_signal_inversion: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_9_DEVELOPMENT_EVIDENCE_AND_MATERIALIZE_H4_STRUCTURAL_ROOM_IF_REQUIRED")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
