#!/usr/bin/env python3
"""
M77.19.7.4.13 — Authorized Candidate Validation-Only Evaluation

Scores ONLY frozen candidate/horizon scopes authorized by M77.19.7.4.12
using ONLY the Validation partition 2018-01-01 .. 2022-12-31.

Final Holdout remains unopened.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math, os, statistics, tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.7.4.13-AUTHORIZED-CANDIDATE-VALIDATION-ONLY-EVALUATION-1.0"
EXPECTED_GATE_VERSION="M77.19.7.4.12-PROSPECTIVE-BEARISH-CANDIDATE-ADVANCEMENT-GATE-1.0"
EXPECTED_H4_VERSION="M77.19.7.4.10-H4-PIT-STRUCTURAL-DOWNSIDE-ROOM-MATERIALIZATION-AUTHORITY-1.0"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"
MIN_VALIDATION_COUNT=300

AUTHORIZED={
    "H2_BREAKDOWN_INITIATION":(5,10),
    "H4_ROOM_PCT_GE_10PCT":(5,10,20),
    "H4_ROOM_PCT_5_10PCT":(5,10,20),
}

class ValidationError(RuntimeError): pass

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
    return q if q.exists() else p

def iter_jsonl(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise ValidationError(f"{path}:{i}: invalid JSONL") from exc

def parse_bool(v:Any)->bool:
    if isinstance(v,bool):return v
    return str(v).strip().lower() in ("true","1","yes")

def stats(xs:list[float])->dict[str,Any]:
    if not xs:return {"count":0,"accuracy":None,"mean":None,"median":None}
    return {
        "count":len(xs),
        "accuracy":sum(x>0 for x in xs)/len(xs),
        "mean":statistics.fmean(xs),
        "median":statistics.median(xs),
    }

def is_validation(as_of:str)->bool:
    d=as_of[:10]
    return VALIDATION_START <= d <= VALIDATION_END

def h2_match(row:Mapping[str,Any])->bool:
    return (
        str(row.get("native_direction","")).upper() in ("BEARISH","STRONG_BEARISH")
        and str(row.get("breakout_state","")).upper()=="BREAKDOWN_SETUP"
        and int(float(row.get("bearish_streak_observations") or 0))<=2
    )

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
    ap.add_argument("--gate-json",default="reports/m77_19_7_4_12_prospective_bearish_candidate_advancement_gate.json")
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--lifecycle-csv",default="reports/m77_19_7_4_6_bearish_lifecycle_observation_evidence.csv")
    ap.add_argument("--h4-authority-json",default="reports/m77_19_7_4_10_h4_point_in_time_structural_downside_room_materialization_authority.json")
    ap.add_argument("--h4-root",default="research_data/m77_19_7_4_10/h4_point_in_time_structural_downside_room")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_13_authorized_candidate_validation_only_evaluation.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_13_validation_candidate_evidence.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    gp=resolve(root,args.gate_json);op=resolve(root,args.outcome_authority_json)
    lc=resolve(root,args.lifecycle_csv);hp=resolve(root,args.h4_authority_json)

    gate=load_json(gp);h4=load_json(hp);outcome=load_json(op)
    if gate.get("version")!=EXPECTED_GATE_VERSION or gate.get("status")!="READY":
        raise ValidationError("advancement gate invalid")
    if h4.get("version")!=EXPECTED_H4_VERSION or h4.get("status")!="READY":
        raise ValidationError("H4 authority invalid")
    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:raise ValidationError("outcome SHA mismatch")

    if gate.get("validation_scope_authorized") != {
        "H2_BREAKDOWN_INITIATION":[5,10],
        "H4_ROOM_PCT_GE_10PCT":[5,10,20],
        "H4_ROOM_PCT_5_10PCT":[5,10,20],
    }:
        raise ValidationError("authorized scope differs from frozen M77.19.7.4.12 gate")

    buckets=defaultdict(lambda:defaultdict(list))
    baselines=defaultdict(list)

    # H2 from lifecycle CSV; only validation dates are consumed.
    with lc.open("r",encoding="utf-8",newline="") as fh:
        r=csv.DictReader(fh)
        for row in r:
            if not is_validation(row["as_of"]):continue
            h=int(row["horizon_sessions"])
            if h not in (5,10,20):continue
            y=float(row["realized_bearish_directional_return"])
            baselines[h].append(y)
            if h in AUTHORIZED["H2_BREAKDOWN_INITIATION"] and h2_match(row):
                buckets["H2_BREAKDOWN_INITIATION"][h].append(y)

    # H4 geometry index from validation partition only.
    geom={}
    for sm in h4.get("symbols") or []:
        symbol=str(sm["symbol"])
        f=resolve(root,sm["materialization_file"])
        if sha256_file(f)!=sm["materialization_sha256"]:
            raise ValidationError(f"{symbol}: H4 materialization SHA mismatch")
        for row in iter_jsonl(f):
            if row.get("partition")!="VALIDATION":continue
            geom[(symbol,str(row["as_of"])[:10])] = row

    oms={str(x["symbol"]):x for x in outcome.get("symbols") or []}
    for symbol,om in oms.items():
        of=resolve(root,om["outcome_file"])
        if sha256_file(of)!=om["outcome_sha256"]:
            raise ValidationError(f"{symbol}: outcome SHA mismatch")
        for row in iter_jsonl(of):
            as_of=str(row["as_of"])[:10]
            if not is_validation(as_of):continue
            g=geom.get((symbol,as_of))
            if g is None:continue
            pct_bin=g.get("nearest_structural_room_pct_bin")
            for h in (5,10,20):
                o=(row.get("outcomes") or {}).get(str(h)) or {}
                if o.get("status")!="MATURED":continue
                y=-float(o["forward_return"])
                if pct_bin=="GE_10PCT":
                    buckets["H4_ROOM_PCT_GE_10PCT"][h].append(y)
                elif pct_bin=="5_10PCT":
                    buckets["H4_ROOM_PCT_5_10PCT"][h].append(y)

    evidence=[]
    for cid,horizons in AUTHORIZED.items():
        for h in horizons:
            s=stats(buckets[cid][h]);b=stats(baselines[h])
            # Validation pass is descriptive governance: adequate sample and both
            # accuracy > 50% and positive median. No threshold optimization.
            pass_gate = (
                s["count"]>=MIN_VALIDATION_COUNT
                and s["accuracy"] is not None and s["accuracy"]>0.5
                and s["median"] is not None and s["median"]>0
            )
            evidence.append({
                "candidate_id":cid,"horizon_sessions":h,**s,
                "baseline_accuracy":b["accuracy"],"baseline_median":b["median"],
                "accuracy_delta_vs_validation_bearish":None if s["accuracy"] is None else s["accuracy"]-b["accuracy"],
                "median_delta_vs_validation_bearish":None if s["median"] is None else s["median"]-b["median"],
                "minimum_validation_count":MIN_VALIDATION_COUNT,
                "validation_pass":pass_gate,
            })

    candidate_summary={}
    for cid,horizons in AUTHORIZED.items():
        rows=[x for x in evidence if x["candidate_id"]==cid]
        candidate_summary[cid]={
            "authorized_horizons":list(horizons),
            "passed_horizons":[x["horizon_sessions"] for x in rows if x["validation_pass"]],
            "failed_horizons":[x["horizon_sessions"] for x in rows if not x["validation_pass"]],
            "all_authorized_horizons_pass":all(x["validation_pass"] for x in rows),
        }

    report={
        "version":VERSION,"status":"READY",
        "gate_authority_sha256":sha256_file(gp),
        "outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "h4_authority_sha256":sha256_file(hp),
        "validation_start":VALIDATION_START,"validation_end":VALIDATION_END,
        "minimum_validation_count":MIN_VALIDATION_COUNT,
        "authorized_scope":{k:list(v) for k,v in AUTHORIZED.items()},
        "evidence":evidence,
        "candidate_summary":candidate_summary,
        "evaluation_scope":{
            "validation_partition_only":True,
            "development_used_for_validation_scoring":False,
            "final_holdout_used_for_validation_scoring":False,
            "final_holdout_opened":False,
            "candidate_definitions_changed":False,
            "thresholds_changed":False,
            "champion_selected":False,
        },
        "governance":{
            "threshold_search_or_optimization":False,
            "parameter_fitting":False,"classifier_training":False,"calibrator_fitting":False,
            "automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"REVIEW_M77_19_7_4_13_VALIDATION_EVIDENCE_BEFORE_ANY_FINAL_HOLDOUT_OPEN",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(evidence[0].keys())
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(evidence)

    print("=== M77.19.7.4.13 AUTHORIZED CANDIDATE VALIDATION-ONLY EVALUATION ===")
    print("status: READY")
    print(f"validation_window: {VALIDATION_START} .. {VALIDATION_END}")
    for e in evidence:
        print(f"{e['candidate_id']}_h{e['horizon_sessions']}: count={e['count']} accuracy={e['accuracy']} median={e['median']} "
              f"accuracy_delta={e['accuracy_delta_vs_validation_bearish']} median_delta={e['median_delta_vs_validation_bearish']} "
              f"validation_pass={e['validation_pass']}")
    for cid,s in candidate_summary.items():
        print(f"{cid}: passed_horizons={s['passed_horizons']} failed_horizons={s['failed_horizons']} all_pass={s['all_authorized_horizons_pass']}")
    print("development_used_for_validation_scoring: False")
    print("final_holdout_used_for_validation_scoring: False")
    print("final_holdout_opened: False")
    print("candidate_definitions_changed: False")
    print("thresholds_changed: False")
    print("champion_selected: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_13_VALIDATION_EVIDENCE_BEFORE_ANY_FINAL_HOLDOUT_OPEN")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
