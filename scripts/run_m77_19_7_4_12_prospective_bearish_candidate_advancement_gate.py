#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json, os, tempfile
from pathlib import Path
from typing import Any

VERSION="M77.19.7.4.12-PROSPECTIVE-BEARISH-CANDIDATE-ADVANCEMENT-GATE-1.0"
EXPECTED_DEV_CANDIDATE_VERSION="M77.19.7.4.9-DEVELOPMENT-ONLY-PROSPECTIVE-BEARISH-EDGE-CANDIDATE-EVALUATION-1.0"
EXPECTED_H4_DEV_VERSION="M77.19.7.4.11-H4-DEVELOPMENT-ONLY-STRUCTURAL-ROOM-EVALUATION-1.0"
EXPECTED_HOLDOUT_VERSION="M77.19.7.4.8-PROSPECTIVE-BEARISH-EDGE-HYPOTHESIS-REGISTRY-TEMPORAL-HOLDOUT-AUTHORITY-1.0"

MIN_INTERPRETABLE_COUNT=500

# Frozen advancement decisions based strictly on already-completed Development evidence.
ADVANCEMENT={
    "H1_FRESH_DOWNSIDE_TRANSITION":"REJECT_DEVELOPMENT",
    "H2_BREAKDOWN_INITIATION":"ADVANCE_VALIDATION_5_10_ONLY",
    "H3_CONTINUATION_WITHOUT_EXHAUSTION":"REJECT_DEVELOPMENT",
    "H4_ROOM_PCT_GE_10PCT":"ADVANCE_VALIDATION_5_10_20",
    "H4_ROOM_PCT_5_10PCT":"ADVANCE_VALIDATION_DIAGNOSTIC",
    "H4_ROOM_ATR_GE_3ATR":"DO_NOT_ADVANCE_INSUFFICIENT_SAMPLE",
    "H4_ROOM_ATR_OTHER":"REJECT_NONMONOTONIC_DEVELOPMENT",
}

class GateError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    p=Path(raw)
    if p.exists():return p
    q=root/p
    return q if q.exists() else p

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def find_candidate_evidence(report:dict[str,Any],cid:str,h:int)->dict[str,Any]:
    rows=report.get("candidate_evidence") or []
    hits=[x for x in rows if x.get("candidate_id")==cid and int(x.get("horizon_sessions"))==h]
    if len(hits)!=1:raise GateError(f"cannot uniquely resolve {cid} h{h}")
    return hits[0]

def find_h4(report:dict[str,Any],family:str,bin_name:str,h:int)->dict[str,Any]:
    rows=report.get("evidence") or []
    hits=[x for x in rows if x.get("family")==family and x.get("bin")==bin_name and int(x.get("horizon_sessions"))==h]
    if len(hits)!=1:raise GateError(f"cannot uniquely resolve {family} {bin_name} h{h}")
    return hits[0]

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--holdout-authority-json",default="reports/m77_19_7_4_8_prospective_bearish_edge_hypothesis_registry_temporal_holdout_authority.json")
    ap.add_argument("--development-candidate-json",default="reports/m77_19_7_4_9_development_only_prospective_bearish_edge_candidate_evaluation.json")
    ap.add_argument("--h4-development-json",default="reports/m77_19_7_4_11_h4_development_only_structural_room_evaluation.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_12_prospective_bearish_candidate_advancement_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_12_candidate_advancement_gate.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    hp=resolve(root,args.holdout_authority_json)
    dp=resolve(root,args.development_candidate_json)
    h4p=resolve(root,args.h4_development_json)

    hold=load_json(hp);dev=load_json(dp);h4=load_json(h4p)
    if hold.get("version")!=EXPECTED_HOLDOUT_VERSION or hold.get("status")!="READY":raise GateError("holdout authority invalid")
    if dev.get("version")!=EXPECTED_DEV_CANDIDATE_VERSION or dev.get("status")!="READY":raise GateError("7.4.9 authority invalid")
    if h4.get("version")!=EXPECTED_H4_DEV_VERSION or h4.get("status")!="READY":raise GateError("7.4.11 authority invalid")

    # Fail-closed evidence assertions for the decisions being frozen.
    h2_5=find_candidate_evidence(dev,"H2_BREAKDOWN_INITIATION",5)
    h2_10=find_candidate_evidence(dev,"H2_BREAKDOWN_INITIATION",10)
    h2_20=find_candidate_evidence(dev,"H2_BREAKDOWN_INITIATION",20)
    if not (h2_5["count"]>=MIN_INTERPRETABLE_COUNT and h2_10["count"]>=MIN_INTERPRETABLE_COUNT):
        raise GateError("H2 5/10 sample below interpretation floor")
    if not (h2_5["accuracy"]>0.5 and h2_5["median"]>0 and h2_10["accuracy"]>0.5 and h2_10["median"]>0):
        raise GateError("H2 5/10 no longer satisfy Development positive-edge authority")
    if h2_20["accuracy"]>=0.5 and h2_20["median"]>0:
        raise GateError("H2 h20 unexpectedly qualifies; gate must be reviewed")

    h4_10_5=find_h4(h4,"ROOM_PCT","GE_10PCT",5)
    h4_10_10=find_h4(h4,"ROOM_PCT","GE_10PCT",10)
    h4_10_20=find_h4(h4,"ROOM_PCT","GE_10PCT",20)
    for x in (h4_10_5,h4_10_10,h4_10_20):
        if x["count"]<MIN_INTERPRETABLE_COUNT:raise GateError("H4 >=10% sample below interpretation floor")
    if not (h4_10_5["accuracy"]>0.5 and h4_10_5["median"]>0):
        raise GateError("H4 >=10% h5 no longer positive")
    if not (h4_10_20["accuracy"]>0.5 and h4_10_20["median"]>0):
        raise GateError("H4 >=10% h20 no longer positive")

    h4_atr3=find_h4(h4,"ROOM_ATR","GE_3ATR",5)
    if h4_atr3["count"]>=MIN_INTERPRETABLE_COUNT:
        raise GateError("H4 >=3ATR is no longer below sample floor; gate must be reviewed")

    gate_rows=[
        {"candidate":"H1_FRESH_DOWNSIDE_TRANSITION","decision":ADVANCEMENT["H1_FRESH_DOWNSIDE_TRANSITION"],"validation_horizons":"","reason":"Development accuracy and median remain weak across all horizons."},
        {"candidate":"H2_BREAKDOWN_INITIATION","decision":ADVANCEMENT["H2_BREAKDOWN_INITIATION"],"validation_horizons":"5,10","reason":"Development h5/h10 both >50% accuracy and positive median; h20 does not qualify."},
        {"candidate":"H3_CONTINUATION_WITHOUT_EXHAUSTION","decision":ADVANCEMENT["H3_CONTINUATION_WITHOUT_EXHAUSTION"],"validation_horizons":"","reason":"Development remains weak across all horizons."},
        {"candidate":"H4_ROOM_PCT_GE_10PCT","decision":ADVANCEMENT["H4_ROOM_PCT_GE_10PCT"],"validation_horizons":"5,10,20","reason":"Pre-frozen >=10% room bin is interpretable and shows strongest Development percent-room evidence."},
        {"candidate":"H4_ROOM_PCT_5_10PCT","decision":ADVANCEMENT["H4_ROOM_PCT_5_10PCT"],"validation_horizons":"5,10,20","reason":"Pre-frozen 5-10% room bin is interpretable and materially improves Development evidence; diagnostic companion to >=10%."},
        {"candidate":"H4_ROOM_ATR_GE_3ATR","decision":ADVANCEMENT["H4_ROOM_ATR_GE_3ATR"],"validation_horizons":"","reason":"Development signal appears positive but count is below fixed 500-observation interpretation floor."},
        {"candidate":"H4_ROOM_ATR_OTHER","decision":ADVANCEMENT["H4_ROOM_ATR_OTHER"],"validation_horizons":"","reason":"Eligible ATR bins are non-monotonic and do not establish robust Development edge."},
    ]

    report={
        "version":VERSION,"status":"READY",
        "holdout_authority_sha256":sha256_file(hp),
        "development_candidate_authority_sha256":sha256_file(dp),
        "h4_development_authority_sha256":sha256_file(h4p),
        "minimum_interpretable_count":MIN_INTERPRETABLE_COUNT,
        "advancement_gate":gate_rows,
        "validation_scope_authorized":{
            "H2_BREAKDOWN_INITIATION":[5,10],
            "H4_ROOM_PCT_GE_10PCT":[5,10,20],
            "H4_ROOM_PCT_5_10PCT":[5,10,20],
        },
        "validation_scope_not_authorized":[
            "H1_FRESH_DOWNSIDE_TRANSITION",
            "H2_BREAKDOWN_INITIATION_h20",
            "H3_CONTINUATION_WITHOUT_EXHAUSTION",
            "H4_ROOM_ATR_GE_3ATR",
            "H4_ROOM_ATR_OTHER",
        ],
        "validation_gate_contract":{
            "validation_may_be_opened_only_for_authorized_candidates_horizons":True,
            "no_candidate_definition_changes_after_validation_open":True,
            "no_threshold_changes_after_validation_open":True,
            "final_holdout_remains_closed":True,
            "validation_success_does_not_authorize_production":True,
        },
        "governance":{
            "development_evidence_recomputed":False,
            "validation_scoring_performed":False,
            "final_holdout_scoring_performed":False,
            "candidate_champion_selected":False,
            "threshold_search_or_optimization":False,
            "parameter_fitting":False,
            "automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_7_4_13_AUTHORIZED_CANDIDATE_VALIDATION_ONLY_EVALUATION",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=["candidate","decision","validation_horizons","reason"]
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(gate_rows)

    print("=== M77.19.7.4.12 PROSPECTIVE BEARISH CANDIDATE ADVANCEMENT GATE ===")
    print("status: READY")
    for r in gate_rows:
        print(f"{r['candidate']}: {r['decision']} validation_horizons={r['validation_horizons']}")
    print("validation_scoring_performed: False")
    print("final_holdout_scoring_performed: False")
    print("candidate_champion_selected: False")
    print("threshold_search_or_optimization: False")
    print("production_model_change_authorized: False")
    print("next_step: BUILD_M77_19_7_4_13_AUTHORIZED_CANDIDATE_VALIDATION_ONLY_EVALUATION")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
