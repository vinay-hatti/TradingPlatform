#!/usr/bin/env python3
"""
M77.19.7.4.10 — H4 Point-in-Time Structural Downside Room Materialization Authority

Research-only materialization for pre-registered H4:
REMAINING_STRUCTURAL_DOWNSIDE_ROOM.

This package DOES NOT score H4 performance. It materializes exact point-in-time
geometry from the full native historical profile and the already-authoritative
historical base close.

No validation or final-holdout candidate scoring occurs here.
"""
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, math, os, tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.7.4.10-H4-PIT-STRUCTURAL-DOWNSIDE-ROOM-MATERIALIZATION-AUTHORITY-1.0"
EXPECTED_REPLAY_SHA="0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
EXPECTED_HOLDOUT_VERSION="M77.19.7.4.8-PROSPECTIVE-BEARISH-EDGE-HYPOTHESIS-REGISTRY-TEMPORAL-HOLDOUT-AUTHORITY-1.0"
EXPECTED_SYMBOLS=602
DEVELOPMENT_END="2017-12-31"

# Neutral reporting bins are frozen here BEFORE H4 performance evaluation.
ROOM_PCT_BINS=((0.0,0.02,"0_2PCT"),(0.02,0.05,"2_5PCT"),(0.05,0.10,"5_10PCT"),(0.10,float("inf"),"GE_10PCT"))
ROOM_ATR_BINS=((0.0,1.0,"0_1ATR"),(1.0,2.0,"1_2ATR"),(2.0,3.0,"2_3ATR"),(3.0,float("inf"),"GE_3ATR"))

class AuthorityError(RuntimeError): pass

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
    for anchor in ("reports","research_data","data"):
        if anchor in p.parts:
            q=root.joinpath(*p.parts[p.parts.index(anchor):])
            if q.exists(): return q
    return p

def iter_jsonl(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise AuthorityError(f"{path}:{i}: invalid JSONL") from exc

def get_path(obj:Any,path:str)->Any:
    cur=obj
    for part in path.split("."):
        if not isinstance(cur,dict) or part not in cur:return None
        cur=cur[part]
    return cur

def numeric(v:Any)->float|None:
    if v is None:return None
    try:x=float(v)
    except Exception:return None
    return x if math.isfinite(x) else None

def extract_price_from_level(x:Any)->float|None:
    if not isinstance(x,dict):return None
    for key in ("price","level","value"):
        v=numeric(x.get(key))
        if v is not None and v>0:return v
    return None

def extract_zone_bounds(x:Any)->tuple[float,float]|None:
    if not isinstance(x,dict):return None
    pairs=(
        ("lower_bound","upper_bound"),
        ("low","high"),
        ("lower","upper"),
        ("bottom","top"),
    )
    for a,b in pairs:
        lo=numeric(x.get(a));hi=numeric(x.get(b))
        if lo is not None and hi is not None and lo>0 and hi>0:
            return (min(lo,hi),max(lo,hi))
    p=extract_price_from_level(x)
    return (p,p) if p is not None else None

def extract_atr(profile:Mapping[str,Any])->tuple[float|None,str|None]:
    # Explicit native-profile candidate paths only. No generic numeric discovery.
    paths=(
        "timeframe_states.1d.evidence.atr",
        "timeframe_states.1d.atr",
        "context.atr",
        "structure.atr",
        "scores.atr",
    )
    hits=[]
    for p in paths:
        v=numeric(get_path(profile,p))
        if v is not None and v>0:hits.append((p,v))
    if not hits:return None,None
    # If multiple explicit aliases exist, they must agree tightly.
    ref=hits[0][1]
    if any(abs(v-ref)>1e-9*max(1.0,abs(ref)) for _,v in hits[1:]):
        raise AuthorityError(f"ambiguous ATR aliases: {hits}")
    return ref,hits[0][0]

def room_bin(x:float|None,bins)->str:
    if x is None:return "UNAVAILABLE"
    if x<0:return "NEGATIVE_INVALID"
    for lo,hi,label in bins:
        if lo<=x<hi:return label
    return "UNAVAILABLE"

def materialize_geometry(profile:Mapping[str,Any], base_close:float)->dict[str,Any]:
    supports=[]
    for x in profile.get("support_levels") or []:
        p=extract_price_from_level(x)
        if p is not None and p < base_close:supports.append(p)
    supports=sorted(set(supports),reverse=True)

    demand=[]
    for x in profile.get("demand_zones") or []:
        b=extract_zone_bounds(x)
        if b is None:continue
        lo,hi=b
        # nearest actionable point below current price is zone upper bound.
        if hi < base_close:demand.append((lo,hi))
        elif lo < base_close <= hi:
            demand.append((lo,base_close))
    demand=sorted(demand,key=lambda z:z[1],reverse=True)

    nearest_support=supports[0] if supports else None
    nearest_demand_upper=demand[0][1] if demand else None
    nearest_candidates=[x for x in (nearest_support,nearest_demand_upper) if x is not None]
    nearest_destination=max(nearest_candidates) if nearest_candidates else None

    second_candidates=[]
    second_candidates.extend(supports[1:2])
    second_candidates.extend([z[1] for z in demand[1:2]])
    second_destination=max(second_candidates) if second_candidates else None

    atr,atr_path=extract_atr(profile)

    def pct_room(dest):
        return None if dest is None else (base_close-dest)/base_close
    def atr_room(dest):
        return None if dest is None or atr is None else (base_close-dest)/atr

    nr=pct_room(nearest_destination)
    nr_atr=atr_room(nearest_destination)
    sr=pct_room(nearest_support)
    dr=pct_room(nearest_demand_upper)
    second=pct_room(second_destination)

    return {
        "support_count_below_price":len(supports),
        "demand_zone_count_below_or_crossing_price":len(demand),
        "nearest_support_price":nearest_support,
        "nearest_demand_upper_price":nearest_demand_upper,
        "nearest_structural_destination_price":nearest_destination,
        "second_structural_destination_price":second_destination,
        "nearest_support_room_pct":sr,
        "nearest_demand_room_pct":dr,
        "nearest_structural_room_pct":nr,
        "second_structural_room_pct":second,
        "atr":atr,
        "atr_source_path":atr_path,
        "nearest_structural_room_atr":nr_atr,
        "nearest_structural_room_pct_bin":room_bin(nr,ROOM_PCT_BINS),
        "nearest_structural_room_atr_bin":room_bin(nr_atr,ROOM_ATR_BINS),
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
    ap.add_argument("--holdout-authority-json",default="reports/m77_19_7_4_8_prospective_bearish_edge_hypothesis_registry_temporal_holdout_authority.json")
    ap.add_argument("--output-root",default="research_data/m77_19_7_4_10/h4_point_in_time_structural_downside_room")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_10_h4_point_in_time_structural_downside_room_materialization_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_10_h4_structural_room_summary.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    rp=resolve(root,args.replay_authority_json);op=resolve(root,args.outcome_authority_json);hp=resolve(root,args.holdout_authority_json)
    if sha256_file(rp)!=EXPECTED_REPLAY_SHA:raise AuthorityError("replay SHA mismatch")
    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:raise AuthorityError("outcome SHA mismatch")
    replay=load_json(rp);outcome=load_json(op);holdout=load_json(hp)
    if replay.get("status")!="READY" or outcome.get("status")!="READY":raise AuthorityError("upstream authority not READY")
    if holdout.get("version")!=EXPECTED_HOLDOUT_VERSION or holdout.get("status")!="READY":raise AuthorityError("holdout authority invalid")

    rms={str(x["symbol"]):x for x in replay.get("symbols") or [] if x.get("cadence")=="WEEKLY"}
    oms={str(x["symbol"]):x for x in outcome.get("symbols") or []}
    if len(rms)!=EXPECTED_SYMBOLS or len(oms)!=EXPECTED_SYMBOLS:raise AuthorityError("symbol count mismatch")

    outroot=Path(args.output_root)
    if not outroot.is_absolute():outroot=root/outroot
    outroot.mkdir(parents=True,exist_ok=True)

    symbol_summary=[]
    aggregate=Counter()
    total_rows=0
    dev_rows=0
    val_rows=0
    hold_rows=0

    for symbol in sorted(rms):
        rm=rms[symbol];om=oms[symbol]
        pf=resolve(root,rm["result_file"])
        of=resolve(root,om["outcome_file"])
        if sha256_file(pf)!=rm["result_sha256"]:raise AuthorityError(f"{symbol}: replay result SHA mismatch")
        if sha256_file(of)!=om["outcome_sha256"]:raise AuthorityError(f"{symbol}: outcome result SHA mismatch")

        profiles={}
        for row in iter_jsonl(pf):
            if row.get("status")!="REPLAYED":continue
            p=row.get("profile")
            if not isinstance(p,dict):raise AuthorityError(f"{symbol}: REPLAYED row missing profile")
            profiles[str(row["as_of"])[:10]]=p

        base_by_date={}
        for row in iter_jsonl(of):
            as_of=str(row["as_of"])[:10]
            # base_close is identical across horizons; require first matured/available outcome payload.
            base=None
            for h in ("5","10","20"):
                o=(row.get("outcomes") or {}).get(h) or {}
                v=numeric(o.get("base_close"))
                if v is not None and v>0:
                    base=v;break
            if base is not None:base_by_date[as_of]=base

        rows=[]
        counters=Counter()
        for as_of,p in sorted(profiles.items()):
            direction=str(p.get("direction") or "").upper()
            if direction not in ("BEARISH","STRONG_BEARISH"):continue
            base=base_by_date.get(as_of)
            if base is None:
                counters["missing_base_close"]+=1
                continue
            geom=materialize_geometry(p,base)
            partition="DEVELOPMENT" if as_of<=DEVELOPMENT_END else ("VALIDATION" if as_of<="2022-12-31" else "FINAL_HOLDOUT")
            rec={"symbol":symbol,"as_of":as_of,"partition":partition,"native_direction":direction,"base_close":base,**geom}
            rows.append(rec)
            counters["rows"]+=1
            counters[f"partition_{partition}"]+=1
            counters[f"pct_bin_{geom['nearest_structural_room_pct_bin']}"]+=1
            counters[f"atr_bin_{geom['nearest_structural_room_atr_bin']}"]+=1
            if geom["nearest_structural_destination_price"] is not None:counters["nearest_destination_available"]+=1
            if geom["atr"] is not None:counters["atr_available"]+=1

        outf=outroot/f"{symbol}.jsonl.gz"
        with gzip.open(outf,"wt",encoding="utf-8") as fh:
            for rec in rows:
                fh.write(json.dumps(rec,sort_keys=True,separators=(",",":"))+"\n")
        result_sha=sha256_file(outf)

        symbol_summary.append({
            "symbol":symbol,"row_count":counters["rows"],
            "development_row_count":counters["partition_DEVELOPMENT"],
            "validation_row_count":counters["partition_VALIDATION"],
            "final_holdout_row_count":counters["partition_FINAL_HOLDOUT"],
            "nearest_destination_available_count":counters["nearest_destination_available"],
            "atr_available_count":counters["atr_available"],
            "materialization_file":str(outf),
            "materialization_sha256":result_sha,
        })
        total_rows+=counters["rows"];dev_rows+=counters["partition_DEVELOPMENT"];val_rows+=counters["partition_VALIDATION"];hold_rows+=counters["partition_FINAL_HOLDOUT"]
        aggregate.update(counters)

    report={
        "version":VERSION,"status":"READY",
        "replay_authority_sha256":EXPECTED_REPLAY_SHA,"outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "holdout_authority_sha256":sha256_file(hp),"successful_symbol_count":EXPECTED_SYMBOLS,
        "materialized_bearish_observation_count":total_rows,
        "development_bearish_observation_count":dev_rows,
        "validation_bearish_observation_count":val_rows,
        "final_holdout_bearish_observation_count":hold_rows,
        "nearest_structural_destination_available_count":aggregate["nearest_destination_available"],
        "atr_available_count":aggregate["atr_available"],
        "room_pct_bins":[{"low":lo,"high":None if math.isinf(hi) else hi,"label":label} for lo,hi,label in ROOM_PCT_BINS],
        "room_atr_bins":[{"low":lo,"high":None if math.isinf(hi) else hi,"label":label} for lo,hi,label in ROOM_ATR_BINS],
        "h4_materialization_contract":{
            "base_price_authority":"M77.19.7.4 outcome base_close at same as_of",
            "support_authority":"native full profile support_levels at same as_of",
            "demand_authority":"native full profile demand_zones at same as_of",
            "atr_authority":"explicit native profile ATR aliases only / fail-closed on disagreement",
            "future_structure_used":False,
            "future_outcome_used_for_geometry":False,
        },
        "performance_computation":{
            "h4_accuracy_computed":False,
            "h4_forward_return_statistics_computed":False,
            "h4_candidate_accept_reject_performed":False,
            "validation_candidate_scoring_performed":False,
            "final_holdout_candidate_scoring_performed":False,
        },
        "symbols":symbol_summary,
        "governance":{
            "threshold_search_or_optimization":False,"parameter_fitting":False,"classifier_training":False,
            "automatic_bearish_signal_inversion":False,"production_model_change_authorized":False,
            "production_authority_effect":False,"database_access":"NONE","polygon_api_queried":False,
            "price_history_table_used":False,
        },
        "next_step":"BUILD_M77_19_7_4_11_H4_DEVELOPMENT_ONLY_STRUCTURAL_ROOM_EVALUATION",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)
    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(symbol_summary[0].keys())
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(symbol_summary)

    print("=== M77.19.7.4.10 H4 POINT-IN-TIME STRUCTURAL DOWNSIDE ROOM MATERIALIZATION AUTHORITY ===")
    print("status: READY")
    print(f"successful_symbol_count: {EXPECTED_SYMBOLS}")
    print(f"materialized_bearish_observation_count: {total_rows}")
    print(f"development_bearish_observation_count: {dev_rows}")
    print(f"validation_bearish_observation_count: {val_rows}")
    print(f"final_holdout_bearish_observation_count: {hold_rows}")
    print(f"nearest_structural_destination_available_count: {aggregate['nearest_destination_available']}")
    print(f"atr_available_count: {aggregate['atr_available']}")
    print("room_pct_bins:", [x[2] for x in ROOM_PCT_BINS])
    print("room_atr_bins:", [x[2] for x in ROOM_ATR_BINS])
    print("h4_accuracy_computed: False")
    print("h4_forward_return_statistics_computed: False")
    print("validation_candidate_scoring_performed: False")
    print("final_holdout_candidate_scoring_performed: False")
    print("production_model_change_authorized: False")
    print("next_step: BUILD_M77_19_7_4_11_H4_DEVELOPMENT_ONLY_STRUCTURAL_ROOM_EVALUATION")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    print(f"output_root: {outroot}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
