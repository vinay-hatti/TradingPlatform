#!/usr/bin/env python3
"""
M77.19.7.4.11 — H4 Development-Only Structural Room Evaluation

Evaluates the pre-registered H4 Remaining Structural Downside Room hypothesis
using DEVELOPMENT observations only (as_of <= 2017-12-31), based on the frozen
M77.19.7.4.10 PIT structural-room materialization.

Validation and Final Holdout H4 outcomes are not scored or opened.
"""
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, math, os, statistics, tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

VERSION="M77.19.7.4.11-H4-DEVELOPMENT-ONLY-STRUCTURAL-ROOM-EVALUATION-1.0"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
EXPECTED_H4_VERSION="M77.19.7.4.10-H4-PIT-STRUCTURAL-DOWNSIDE-ROOM-MATERIALIZATION-AUTHORITY-1.0"
EXPECTED_SYMBOLS=602
DEVELOPMENT_END="2017-12-31"
FIXED_HORIZONS=(5,10,20)
PCT_BINS=("0_2PCT","2_5PCT","5_10PCT","GE_10PCT")
ATR_BINS=("0_1ATR","1_2ATR","2_3ATR","GE_3ATR")
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
    if not p.is_absolute():
        q=root/p
        if q.exists(): return q
    return p

def iter_jsonl(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise EvidenceError(f"{path}:{i}: invalid JSONL") from exc

def stats(xs:list[float])->dict[str,Any]:
    if not xs:return {"count":0,"accuracy":None,"mean":None,"median":None,"p25":None,"p75":None}
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
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--h4-authority-json",default="reports/m77_19_7_4_10_h4_point_in_time_structural_downside_room_materialization_authority.json")
    ap.add_argument("--h4-root",default="research_data/m77_19_7_4_10/h4_point_in_time_structural_downside_room")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_11_h4_development_only_structural_room_evaluation.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_11_h4_development_structural_room_evidence.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    op=resolve(root,args.outcome_authority_json)
    hp=resolve(root,args.h4_authority_json)
    h4root=resolve(root,args.h4_root)

    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:raise EvidenceError("outcome authority SHA mismatch")
    outcome=load_json(op);h4=load_json(hp)
    if outcome.get("status")!="READY":raise EvidenceError("outcome authority not READY")
    if h4.get("version")!=EXPECTED_H4_VERSION or h4.get("status")!="READY":raise EvidenceError("H4 authority invalid")
    if h4.get("successful_symbol_count")!=EXPECTED_SYMBOLS:raise EvidenceError("H4 symbol count mismatch")
    if h4.get("development_bearish_observation_count")!=74832:raise EvidenceError("H4 development count authority mismatch")
    if h4.get("nearest_structural_destination_available_count")!=145674:raise EvidenceError("H4 destination count authority mismatch")
    if h4.get("atr_available_count")!=145720:raise EvidenceError("H4 ATR count authority mismatch")

    oms={str(x["symbol"]):x for x in outcome.get("symbols") or []}
    if len(oms)!=EXPECTED_SYMBOLS:raise EvidenceError("outcome symbol count mismatch")

    pct=defaultdict(lambda:defaultdict(list))
    atr=defaultdict(lambda:defaultdict(list))
    all_dev=defaultdict(list)
    no_destination=defaultdict(list)
    joined_observations=0
    skipped_nondev_geometry=0

    for sm in h4.get("symbols") or []:
        symbol=str(sm["symbol"])
        geom_file=resolve(root,sm["materialization_file"])
        if sha256_file(geom_file)!=sm["materialization_sha256"]:
            raise EvidenceError(f"{symbol}: H4 materialization SHA mismatch")

        geometry={}
        for row in iter_jsonl(geom_file):
            if row["partition"]!="DEVELOPMENT":
                skipped_nondev_geometry+=1
                continue
            geometry[str(row["as_of"])[:10]]=row

        om=oms[symbol]
        outcome_file=resolve(root,om["outcome_file"])
        if sha256_file(outcome_file)!=om["outcome_sha256"]:
            raise EvidenceError(f"{symbol}: outcome SHA mismatch")

        for row in iter_jsonl(outcome_file):
            as_of=str(row["as_of"])[:10]
            if as_of>DEVELOPMENT_END:continue
            g=geometry.get(as_of)
            # Outcome authority includes all directions; H4 materialization only bearish.
            if g is None:continue
            joined_observations+=1

            pct_bin=g["nearest_structural_room_pct_bin"]
            atr_bin=g["nearest_structural_room_atr_bin"]

            if pct_bin not in PCT_BINS and pct_bin!="UNAVAILABLE":
                raise EvidenceError(f"{symbol} {as_of}: unexpected pct bin {pct_bin}")
            if atr_bin not in ATR_BINS and atr_bin!="UNAVAILABLE":
                raise EvidenceError(f"{symbol} {as_of}: unexpected ATR bin {atr_bin}")

            for h in FIXED_HORIZONS:
                o=(row.get("outcomes") or {}).get(str(h)) or {}
                if o.get("status")!="MATURED":continue
                y=-float(o["forward_return"])
                all_dev[h].append(y)
                if pct_bin in PCT_BINS:pct[pct_bin][h].append(y)
                else:no_destination[h].append(y)
                if atr_bin in ATR_BINS:atr[atr_bin][h].append(y)

    evidence=[]
    for family,buckets,ordered in (("ROOM_PCT",pct,PCT_BINS),("ROOM_ATR",atr,ATR_BINS)):
        for b in ordered:
            for h in FIXED_HORIZONS:
                s=stats(buckets[b][h]);base=stats(all_dev[h])
                evidence.append({
                    "family":family,"bin":b,"horizon_sessions":h,**s,
                    "baseline_accuracy":base["accuracy"],"baseline_median":base["median"],
                    "accuracy_delta_vs_all_dev_bearish":None if s["accuracy"] is None else s["accuracy"]-base["accuracy"],
                    "median_delta_vs_all_dev_bearish":None if s["median"] is None else s["median"]-base["median"],
                    "eligible_for_interpretation":s["count"]>=MIN_CELL_COUNT,
                })

    # Monotonicity is diagnostic only, using pre-frozen bin order.
    monotonic={}
    for family,ordered in (("ROOM_PCT",PCT_BINS),("ROOM_ATR",ATR_BINS)):
        monotonic[family]={}
        for h in FIXED_HORIZONS:
            rows=[next(x for x in evidence if x["family"]==family and x["bin"]==b and x["horizon_sessions"]==h) for b in ordered]
            valid=[r for r in rows if r["eligible_for_interpretation"]]
            acc=[r["accuracy"] for r in valid]
            med=[r["median"] for r in valid]
            monotonic[family][str(h)]={
                "eligible_bin_count":len(valid),
                "accuracy_non_decreasing_with_more_room":len(acc)>=2 and all(acc[i+1]>=acc[i] for i in range(len(acc)-1)),
                "median_non_decreasing_with_more_room":len(med)>=2 and all(med[i+1]>=med[i] for i in range(len(med)-1)),
            }

    report={
        "version":VERSION,"status":"READY",
        "outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "h4_materialization_authority_sha256":sha256_file(hp),
        "successful_symbol_count":EXPECTED_SYMBOLS,
        "development_end":DEVELOPMENT_END,
        "joined_development_bearish_observation_count":joined_observations,
        "nondevelopment_geometry_rows_seen_and_skipped":skipped_nondev_geometry,
        "fixed_horizons_sessions":list(FIXED_HORIZONS),
        "minimum_interpretation_cell_count":MIN_CELL_COUNT,
        "evidence":evidence,
        "monotonicity_diagnostics":monotonic,
        "evaluation_scope":{
            "development_partition_only":True,
            "validation_candidate_scoring_performed":False,
            "final_holdout_candidate_scoring_performed":False,
            "validation_opened":False,
            "final_holdout_opened":False,
            "h4_champion_selected":False,
        },
        "governance":{
            "bins_pre_frozen_by_m77_19_7_4_10":True,
            "threshold_search_or_optimization":False,
            "parameter_fitting":False,
            "classifier_training":False,
            "calibrator_fitting":False,
            "automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"REVIEW_M77_19_7_4_11_H4_DEVELOPMENT_EVIDENCE_AND_FREEZE_CANDIDATE_ADVANCEMENT_GATE",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(evidence[0].keys())
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(evidence)

    print("=== M77.19.7.4.11 H4 DEVELOPMENT-ONLY STRUCTURAL ROOM EVALUATION ===")
    print("status: READY")
    print(f"joined_development_bearish_observation_count: {joined_observations}")
    print(f"nondevelopment_geometry_rows_seen_and_skipped: {skipped_nondev_geometry}")
    for family,ordered in (("ROOM_PCT",PCT_BINS),("ROOM_ATR",ATR_BINS)):
        for h in FIXED_HORIZONS:
            for b in ordered:
                r=next(x for x in evidence if x["family"]==family and x["bin"]==b and x["horizon_sessions"]==h)
                print(f"{family}_{b}_h{h}: count={r['count']} accuracy={r['accuracy']} median={r['median']} "
                      f"accuracy_delta={r['accuracy_delta_vs_all_dev_bearish']} median_delta={r['median_delta_vs_all_dev_bearish']} "
                      f"eligible={r['eligible_for_interpretation']}")
            print(f"{family}_h{h}_monotonicity: {monotonic[family][str(h)]}")
    print("validation_candidate_scoring_performed: False")
    print("final_holdout_candidate_scoring_performed: False")
    print("h4_champion_selected: False")
    print("threshold_search_or_optimization: False")
    print("parameter_fitting: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_11_H4_DEVELOPMENT_EVIDENCE_AND_FREEZE_CANDIDATE_ADVANCEMENT_GATE")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
