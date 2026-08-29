#!/usr/bin/env python3
"""
M77.19.7.4.14 — Development-to-Validation Regime Shift & Edge Instability Forensics

Diagnostic-only analysis of already-frozen candidate behavior across:
- DEVELOPMENT <= 2017-12-31
- VALIDATION 2018-01-01 .. 2022-12-31

Final Holdout >= 2023-01-01 remains sealed and is not read for candidate scoring.
No new candidate is introduced, fitted, ranked, or promoted.
"""
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, math, os, statistics, tempfile
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.7.4.14-DEVELOPMENT-VALIDATION-REGIME-SHIFT-EDGE-INSTABILITY-FORENSICS-1.0"
EXPECTED_GATE_VERSION="M77.19.7.4.12-PROSPECTIVE-BEARISH-CANDIDATE-ADVANCEMENT-GATE-1.0"
EXPECTED_VALIDATION_VERSION="M77.19.7.4.13-AUTHORIZED-CANDIDATE-VALIDATION-ONLY-EVALUATION-1.0"
EXPECTED_H4_VERSION="M77.19.7.4.10-H4-PIT-STRUCTURAL-DOWNSIDE-ROOM-MATERIALIZATION-AUTHORITY-1.0"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"

DEV_END="2017-12-31"
VAL_START="2018-01-01"
VAL_END="2022-12-31"
FINAL_HOLDOUT_START="2023-01-01"
HORIZONS=(5,10,20)

class ForensicError(RuntimeError): pass

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
            try: yield json.loads(line)
            except Exception as exc: raise ForensicError(f"{path}:{i}: invalid JSONL") from exc

def stats(xs:list[float])->dict[str,Any]:
    if not xs:
        return {"count":0,"accuracy":None,"median":None,"mean":None}
    return {
        "count":len(xs),
        "accuracy":sum(x>0 for x in xs)/len(xs),
        "median":statistics.median(xs),
        "mean":statistics.fmean(xs),
    }

def parse_bool(v:Any)->bool:
    if isinstance(v,bool): return v
    return str(v).strip().lower() in ("true","1","yes")

def h2_match(row:Mapping[str,Any])->bool:
    return (
        str(row.get("native_direction","")).upper() in ("BEARISH","STRONG_BEARISH")
        and str(row.get("breakout_state","")).upper()=="BREAKDOWN_SETUP"
        and int(float(row.get("bearish_streak_observations") or 0))<=2
    )

def era(as_of:str)->str|None:
    d=as_of[:10]
    if d<=DEV_END:return "DEVELOPMENT"
    if VAL_START<=d<=VAL_END:return "VALIDATION"
    return None

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent); os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True); fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--gate-json",default="reports/m77_19_7_4_12_prospective_bearish_candidate_advancement_gate.json")
    ap.add_argument("--validation-json",default="reports/m77_19_7_4_13_authorized_candidate_validation_only_evaluation.json")
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--lifecycle-csv",default="reports/m77_19_7_4_6_bearish_lifecycle_observation_evidence.csv")
    ap.add_argument("--h4-authority-json",default="reports/m77_19_7_4_10_h4_point_in_time_structural_downside_room_materialization_authority.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_14_development_validation_regime_shift_edge_instability_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_14_year_candidate_evidence.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    gp=resolve(root,args.gate_json); vp=resolve(root,args.validation_json)
    op=resolve(root,args.outcome_authority_json); lc=resolve(root,args.lifecycle_csv)
    hp=resolve(root,args.h4_authority_json)

    gate=load_json(gp); val=load_json(vp); outcome=load_json(op); h4=load_json(hp)
    if gate.get("version")!=EXPECTED_GATE_VERSION or gate.get("status")!="READY":
        raise ForensicError("gate authority invalid")
    if val.get("version")!=EXPECTED_VALIDATION_VERSION or val.get("status")!="READY":
        raise ForensicError("validation authority invalid")
    if h4.get("version")!=EXPECTED_H4_VERSION or h4.get("status")!="READY":
        raise ForensicError("H4 authority invalid")
    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:
        raise ForensicError("outcome authority SHA mismatch")

    # Candidate-year-horizon realized bearish returns.
    by=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    universe_year=defaultdict(lambda:defaultdict(list))
    symbol_presence=defaultdict(lambda:defaultdict(set))

    # H2 from already-materialized lifecycle evidence, restricted to Dev+Val only.
    with lc.open("r",encoding="utf-8",newline="") as fh:
        r=csv.DictReader(fh)
        for row in r:
            e=era(row["as_of"])
            if e is None: continue
            h=int(row["horizon_sessions"])
            if h not in HORIZONS: continue
            y=float(row["realized_bearish_directional_return"])
            yr=int(row["as_of"][:4])
            universe_year[yr][h].append(y)
            if h2_match(row) and h in (5,10):
                by["H2_BREAKDOWN_INITIATION"][yr][h].append(y)
                symbol_presence["H2_BREAKDOWN_INITIATION"][yr].add(str(row["symbol"]))

    # H4 geometry only indexed for Dev+Val. Final holdout rows are skipped without scoring.
    geom={}
    final_holdout_geometry_rows_skipped=0
    for sm in h4.get("symbols") or []:
        symbol=str(sm["symbol"])
        f=resolve(root,sm["materialization_file"])
        if sha256_file(f)!=sm["materialization_sha256"]:
            raise ForensicError(f"{symbol}: H4 SHA mismatch")
        for row in iter_jsonl(f):
            e=era(str(row["as_of"]))
            if e is None:
                if str(row["as_of"])[:10]>=FINAL_HOLDOUT_START:
                    final_holdout_geometry_rows_skipped += 1
                continue
            geom[(symbol,str(row["as_of"])[:10])] = row

    oms={str(x["symbol"]):x for x in outcome.get("symbols") or []}
    final_holdout_outcome_rows_skipped=0
    for symbol,sm in oms.items():
        of=resolve(root,sm["outcome_file"])
        if sha256_file(of)!=sm["outcome_sha256"]:
            raise ForensicError(f"{symbol}: outcome SHA mismatch")
        for row in iter_jsonl(of):
            as_of=str(row["as_of"])[:10]
            e=era(as_of)
            if e is None:
                if as_of>=FINAL_HOLDOUT_START:
                    final_holdout_outcome_rows_skipped += 1
                continue
            g=geom.get((symbol,as_of))
            if g is None: continue
            b=g.get("nearest_structural_room_pct_bin")
            if b not in ("GE_10PCT","5_10PCT"): continue
            cid="H4_ROOM_PCT_GE_10PCT" if b=="GE_10PCT" else "H4_ROOM_PCT_5_10PCT"
            yr=int(as_of[:4])
            for h in HORIZONS:
                o=(row.get("outcomes") or {}).get(str(h)) or {}
                if o.get("status")!="MATURED": continue
                y=-float(o["forward_return"])
                by[cid][yr][h].append(y)
                symbol_presence[cid][yr].add(symbol)

    year_rows=[]
    years=sorted(set(list(universe_year.keys()) + [y for c in by.values() for y in c.keys()]))
    for cid,yrmap in by.items():
        for yr,hmap in sorted(yrmap.items()):
            era_name="DEVELOPMENT" if yr<=2017 else "VALIDATION"
            for h,xs in sorted(hmap.items()):
                s=stats(xs); base=stats(universe_year[yr][h])
                year_rows.append({
                    "candidate_id":cid,
                    "era":era_name,
                    "year":yr,
                    "horizon_sessions":h,
                    **s,
                    "baseline_accuracy":base["accuracy"],
                    "baseline_median":base["median"],
                    "accuracy_delta_vs_year_bearish":None if s["accuracy"] is None else s["accuracy"]-base["accuracy"],
                    "median_delta_vs_year_bearish":None if s["median"] is None else s["median"]-base["median"],
                    "symbol_count":len(symbol_presence[cid][yr]),
                })

    # Era-level and instability diagnostics.
    era_rows=[]
    instability={}
    for cid in ("H2_BREAKDOWN_INITIATION","H4_ROOM_PCT_GE_10PCT","H4_ROOM_PCT_5_10PCT"):
        instability[cid]={}
        horizons=(5,10) if cid=="H2_BREAKDOWN_INITIATION" else HORIZONS
        for h in horizons:
            dev=[]
            vr=[]
            for yr,hmap in by[cid].items():
                target=dev if yr<=2017 else vr
                target.extend(hmap.get(h,[]))
            ds=stats(dev); vs=stats(vr)
            era_rows.extend([
                {"candidate_id":cid,"era":"DEVELOPMENT","horizon_sessions":h,**ds},
                {"candidate_id":cid,"era":"VALIDATION","horizon_sessions":h,**vs},
            ])
            dev_years=[r for r in year_rows if r["candidate_id"]==cid and r["horizon_sessions"]==h and r["era"]=="DEVELOPMENT" and r["count"]>0]
            val_years=[r for r in year_rows if r["candidate_id"]==cid and r["horizon_sessions"]==h and r["era"]=="VALIDATION" and r["count"]>0]
            instability[cid][str(h)]={
                "development_accuracy":ds["accuracy"],
                "validation_accuracy":vs["accuracy"],
                "accuracy_shift_validation_minus_development":None if ds["accuracy"] is None or vs["accuracy"] is None else vs["accuracy"]-ds["accuracy"],
                "development_median":ds["median"],
                "validation_median":vs["median"],
                "median_shift_validation_minus_development":None if ds["median"] is None or vs["median"] is None else vs["median"]-ds["median"],
                "development_positive_year_count":sum((r["accuracy"] or 0)>0.5 and (r["median"] or 0)>0 for r in dev_years),
                "development_year_count":len(dev_years),
                "validation_positive_year_count":sum((r["accuracy"] or 0)>0.5 and (r["median"] or 0)>0 for r in val_years),
                "validation_year_count":len(val_years),
                "sign_reversal":(
                    ds["median"] is not None and vs["median"] is not None
                    and ((ds["median"]>0 and vs["median"]<0) or (ds["median"]<0 and vs["median"]>0))
                ),
            }

    # Concentration diagnostics: identify whether candidate edge was isolated to a small set of years.
    concentration={}
    for cid in instability:
        concentration[cid]={}
        horizons=(5,10) if cid=="H2_BREAKDOWN_INITIATION" else HORIZONS
        for h in horizons:
            rows=[r for r in year_rows if r["candidate_id"]==cid and r["horizon_sessions"]==h and r["era"]=="DEVELOPMENT" and r["count"]>0]
            top=sorted(rows,key=lambda r:((r["median"] if r["median"] is not None else -999),r["count"]),reverse=True)[:5]
            concentration[cid][str(h)]={
                "top_development_years_by_median":[
                    {"year":r["year"],"count":r["count"],"accuracy":r["accuracy"],"median":r["median"],"symbol_count":r["symbol_count"]}
                    for r in top
                ]
            }

    report={
        "version":VERSION,"status":"READY",
        "gate_authority_sha256":sha256_file(gp),
        "validation_authority_sha256":sha256_file(vp),
        "outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "h4_authority_sha256":sha256_file(hp),
        "analysis_windows":{
            "development_end":DEV_END,
            "validation_start":VAL_START,
            "validation_end":VAL_END,
            "final_holdout_start":FINAL_HOLDOUT_START,
        },
        "year_candidate_evidence":year_rows,
        "era_candidate_evidence":era_rows,
        "edge_instability":instability,
        "development_year_concentration":concentration,
        "forensic_findings":{
            "all_authorized_candidates_failed_validation":all(
                not x.get("validation_pass",False) for x in (val.get("evidence") or [])
            ),
            "development_validation_instability_present":any(
                z.get("sign_reversal",False)
                or (z.get("accuracy_shift_validation_minus_development") is not None and z["accuracy_shift_validation_minus_development"]<-0.05)
                for c in instability.values() for z in c.values()
            ),
            "final_holdout_remains_sealed":True,
            "new_candidate_introduced":False,
        },
        "holdout_protection":{
            "final_holdout_geometry_rows_seen_and_skipped":final_holdout_geometry_rows_skipped,
            "final_holdout_outcome_rows_seen_and_skipped":final_holdout_outcome_rows_skipped,
            "final_holdout_candidate_scoring_performed":False,
        },
        "governance":{
            "new_candidate_definition":False,
            "threshold_search_or_optimization":False,
            "parameter_fitting":False,
            "classifier_training":False,
            "calibrator_fitting":False,
            "automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"REVIEW_M77_19_7_4_14_REGIME_INSTABILITY_BEFORE_ANY_NEW_PROSPECTIVE_EDGE_HYPOTHESIS",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(year_rows[0].keys()) if year_rows else ["candidate_id","era","year","horizon_sessions"]
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(year_rows)

    print("=== M77.19.7.4.14 DEVELOPMENT-TO-VALIDATION REGIME SHIFT & EDGE INSTABILITY FORENSICS ===")
    print("status: READY")
    print(f"all_authorized_candidates_failed_validation: {report['forensic_findings']['all_authorized_candidates_failed_validation']}")
    print(f"development_validation_instability_present: {report['forensic_findings']['development_validation_instability_present']}")
    for cid,c in instability.items():
        for h,z in c.items():
            print(f"{cid}_h{h}: dev_acc={z['development_accuracy']} val_acc={z['validation_accuracy']} acc_shift={z['accuracy_shift_validation_minus_development']} "
                  f"dev_median={z['development_median']} val_median={z['validation_median']} median_shift={z['median_shift_validation_minus_development']} "
                  f"dev_positive_years={z['development_positive_year_count']}/{z['development_year_count']} "
                  f"val_positive_years={z['validation_positive_year_count']}/{z['validation_year_count']} sign_reversal={z['sign_reversal']}")
    print(f"final_holdout_geometry_rows_seen_and_skipped: {final_holdout_geometry_rows_skipped}")
    print(f"final_holdout_outcome_rows_seen_and_skipped: {final_holdout_outcome_rows_skipped}")
    print("final_holdout_candidate_scoring_performed: False")
    print("new_candidate_introduced: False")
    print("threshold_search_or_optimization: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_14_REGIME_INSTABILITY_BEFORE_ANY_NEW_PROSPECTIVE_EDGE_HYPOTHESIS")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
