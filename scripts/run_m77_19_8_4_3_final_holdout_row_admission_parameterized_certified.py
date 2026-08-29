#!/usr/bin/env python3
"""
M77.19.8.4.3 — Certified Source Resolver Development Feature Backfill Repair

Rebuilds the Development-only feature matrix using the certified source
contracts from M77.19.8.4.2:

Reference price:
  profile.timeframe_states.1d.close

Frozen daily source:
  **/<symbol>.daily.csv.gz
  session_date
  close

Backfilled feature IDs:
  F020, F021, F030, F031, F070, F080, F081

Still not materialized:
  F012 / F051 -> census only
  F071 -> blocked pending PIT sector authority

No outcome/target files are opened.
No Validation/Final Holdout feature rows are materialized.
No model is trained/scored.
Production authority remains unchanged.
"""
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, math, os, tempfile
from collections import Counter
from bisect import bisect_right
from pathlib import Path
from typing import Any, Iterable

VERSION="M77.19.8.4.3-CERTIFIED-SOURCE-RESOLVER-DEVELOPMENT-FEATURE-BACKFILL-REPAIR-1.0"
EXPECTED_842_VERSION="M77.19.8.4.2-REFERENCE-PRICE-FROZEN-DAILY-SOURCE-RESOLVER-AUTHORITY-1.0"
EXPECTED_84_VERSION="M77.19.8.4-BLOCKED-FEATURE-SCHEMA-CENSUS-DEVELOPMENT-FEATURE-BACKFILL-AUTHORITY-1.0"

DEV_END="2017-12-31"
VALIDATION_START="2018-01-01"
FINAL_HOLDOUT_START="2023-01-01"

REFERENCE_PRICE_PATH="profile.timeframe_states.1d.close"
DATE_FIELD="session_date"
CLOSE_FIELD="close"

BACKFILL_FEATURES=["F020","F021","F030","F031","F070","F080","F081"]
CENSUS_ONLY_FEATURES=["F012","F051"]
STILL_BLOCKED_FEATURES=["F071"]

class RepairError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    p=Path(raw).expanduser()
    if p.is_absolute(): return p.resolve()
    return (root/p).resolve()

def iter_jsonl_gz(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip(): continue
            try: yield json.loads(line)
            except Exception as exc: raise RepairError(f"{path}:{i}: invalid JSONL") from exc

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def write_jsonl_gz(path:Path,rows:list[dict[str,Any]]):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with gzip.open(tmp,"wt",encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def get_path(obj:Any,path:str):
    cur=obj
    for part in path.split("."):
        if not isinstance(cur,dict) or part not in cur:return None
        cur=cur[part]
    return cur

def to_float(v):
    if v is None or isinstance(v,bool): return None
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None

def extract_level_price(level:Any):
    if isinstance(level,(int,float)): return to_float(level)
    if not isinstance(level,dict): return None
    for k in ("price","level","value"):
        if k in level:
            v=to_float(level.get(k))
            if v is not None:return v
    return None

def nearest_distance(levels:Any,ref:float):
    vals=[]
    for x in levels or []:
        v=extract_level_price(x)
        if v is not None:vals.append(v)
    if not vals:return None
    nearest=min(vals,key=lambda v:abs(v-ref))
    return (nearest-ref)/ref

def unique_native_atr_1d(profile:dict[str,Any]):
    ts=profile.get("timeframe_states") or {}
    one=ts.get("1d") if isinstance(ts,dict) else None
    if not isinstance(one,dict):return None
    hits=[]
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if "atr" in str(k).lower():
                    fv=to_float(v)
                    if fv is not None:hits.append(fv)
                if isinstance(v,dict):walk(v)
    walk(one)
    uniq=sorted(set(round(v,14) for v in hits))
    if len(uniq)==1:return float(uniq[0])
    return None

def load_daily_csv(path:Path):
    rows=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as fh:
        reader=csv.DictReader(fh)
        fields=reader.fieldnames or []
        if DATE_FIELD not in fields or CLOSE_FIELD not in fields:
            raise RepairError(f"{path}: certified fields missing; fields={fields}")
        for i,r in enumerate(reader,2):
            d=str(r.get(DATE_FIELD) or "")[:10]
            c=to_float(r.get(CLOSE_FIELD))
            if not d or c is None or c<=0:
                continue
            rows.append((d,c))
    rows.sort()
    # same-date duplicates are fail-closed if prices conflict
    dedup=[]
    for d,c in rows:
        if dedup and dedup[-1][0]==d:
            if abs(dedup[-1][1]-c)>1e-12*max(1.0,abs(c),abs(dedup[-1][1])):
                raise RepairError(f"{path}: conflicting duplicate close for {d}")
            continue
        dedup.append((d,c))
    return dedup

def daily_file_map(root:Path):
    files=sorted(root.rglob("*.daily.csv.gz"))
    mapping={}
    for p in files:
        symbol=p.name[:-len(".daily.csv.gz")]
        if symbol in mapping:
            raise RepairError(f"ambiguous daily file mapping for {symbol}")
        mapping[symbol]=p
    return mapping

def prefix_close_on_or_before(hist:list[tuple[str,float]],as_of:str):
    dates=[d for d,_ in hist]
    i=bisect_right(dates,as_of)-1
    if i<0:return None,None
    return i,hist[i][1]

def trailing_return_by_sessions(hist:list[tuple[str,float]],as_of:str,sessions:int):
    i,c=prefix_close_on_or_before(hist,as_of)
    if i is None or i-sessions<0:return None
    base=hist[i-sessions][1]
    return c/base-1 if base else None

def trailing_52w_location(hist:list[tuple[str,float]],as_of:str):
    i,c=prefix_close_on_or_before(hist,as_of)
    if i is None:return {}
    window=hist[max(0,i-251):i+1]
    if len(window)<2:return {}
    peak=max(v for _,v in window)
    low=min(v for _,v in window)
    return {
        "F080":c/peak-1 if peak else None,
        "F081":c/low-1 if low else None,
    }

def relative_strength(hist,spy_hist,as_of):
    s13=trailing_return_by_sessions(hist,as_of,65)
    m13=trailing_return_by_sessions(spy_hist,as_of,65)
    s26=trailing_return_by_sessions(hist,as_of,130)
    m26=trailing_return_by_sessions(spy_hist,as_of,130)
    if s13 is None and s26 is None:return None
    return {
        "rs_13w":None if s13 is None or m13 is None else s13-m13,
        "rs_26w":None if s26 is None or m26 is None else s26-m26,
    }

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--active-partition-start",default="")
    ap.add_argument("--active-partition-end",default="2017-12-31")
    ap.add_argument("--active-partition-label",default="DEVELOPMENT")
    ap.add_argument("--expected-matrix-symbol-count",type=int,default=524)
    ap.add_argument("--expected-matrix-row-count",type=int,default=303689)
    ap.add_argument("--partition-end",default="2017-12-31")
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--backfill-authority-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--matrix-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--output-json",default="reports/m77_19_8_4_3_certified_source_resolver_development_feature_backfill_repair.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_4_3_backfill_coverage_summary.csv")
    args=ap.parse_args()
    # M77.19.8.7.10.5.1.0.3 runtime-only partition override
    globals()["DEV_END"]=args.partition_end

    root=Path(args.project_root).resolve()
    rp=resolve(root,args.resolver_authority_json)
    bp=resolve(root,args.backfill_authority_json)
    mr=resolve(root,args.matrix_root)
    rr=resolve(root,args.replay_root)
    dr=resolve(root,args.daily_materialization_root)
    outroot=resolve(root,args.output_root)

    ra=load_json(rp);ba=load_json(bp)
    if ra.get("version")!=EXPECTED_842_VERSION or ra.get("status")!="READY":
        raise RepairError("M77.19.8.4.2 resolver authority invalid")
    if ba.get("version")!=EXPECTED_84_VERSION or ba.get("status")!="READY":
        raise RepairError("M77.19.8.4 authority invalid")
    rpa=ra.get("reference_price_authority") or {}
    dsa=ra.get("frozen_daily_source_resolver") or {}
    if rpa.get("certified") is not True or rpa.get("preferred_path")!=REFERENCE_PRICE_PATH:
        raise RepairError("reference price authority not certified as expected")
    if dsa.get("certified") is not True:
        raise RepairError("daily resolver authority not certified")
    if dsa.get("date_field")!=DATE_FIELD or dsa.get("close_field")!=CLOSE_FIELD:
        raise RepairError("daily schema differs from certified fields")

    matrix_files=sorted(mr.glob("*.jsonl.gz"))
    if len(matrix_files)!=args.expected_matrix_symbol_count:
        raise RepairError(f"expected {args.expected_matrix_symbol_count} matrix files, found {len(matrix_files)}")
    replay_files={p.name[:-9]:p for p in (rr/"weekly"/"profiles").glob("*.jsonl.gz")}
    if len(replay_files)!=602:raise RepairError("expected 602 replay files")
    daily_map=daily_file_map(dr)
    if len(daily_map)!=602:raise RepairError(f"expected 602 daily files, found {len(daily_map)}")
    spy_hist=load_daily_csv(daily_map["SPY"])

    coverage_present=Counter()
    coverage_missing=Counter()
    missing_reasons=Counter()
    total_rows=0
    symbols=[]
    reference_mismatch_count=0
    validation_rows_materialized=0
    final_holdout_rows_materialized=0

    for mf in matrix_files:
        symbol=mf.name[:-9]
        rf=replay_files.get(symbol)
        df=daily_map.get(symbol)
        if rf is None or df is None:
            raise RepairError(f"{symbol}: certified replay/daily source missing")
        hist=load_daily_csv(df)
        replay_by_date={}
        for r in iter_jsonl_gz(rf):
            d=str(r.get("as_of") or "")[:10]
            if (not args.active_partition_start or d>=args.active_partition_start) and d<=args.active_partition_end and r.get("status")=="REPLAYED":
                replay_by_date[d]=r

        out_rows=[]
        for row in iter_jsonl_gz(mf):
            d=str(row.get("as_of") or "")[:10]
            if d>=FINAL_HOLDOUT_START and args.active_partition_label!="FINAL_HOLDOUT":
                final_holdout_rows_materialized+=1
                continue
            if args.active_partition_label=="DEVELOPMENT" and d>=VALIDATION_START:
                validation_rows_materialized+=1
                continue
            rrw=replay_by_date.get(d)
            if args.active_partition_label in ("VALIDATION","FINAL_HOLDOUT"):
                if d<args.active_partition_start or d>args.active_partition_end:
                    continue
            elif args.active_partition_label=="DEVELOPMENT":
                if args.active_partition_start and d<args.active_partition_start:
                    continue
                if d>args.active_partition_end:
                    continue
            else:
                raise RepairError(f"unsupported active partition label: {args.active_partition_label}")
            if rrw is None:raise RepairError(f"{symbol} {d}: replay provenance missing")
            p=rrw.get("profile") or {}
            if not isinstance(p,dict):raise RepairError(f"{symbol} {d}: full profile missing")

            vals=dict(row.get("feature_values") or {})
            miss=dict(row.get("feature_missing") or {})
            reasons=dict(row.get("feature_missing_reason") or {})

            # F020: preserve/recompute under same preregistered semantics.
            atr=unique_native_atr_1d(p)
            if atr is not None:
                vals["F020"]=atr;miss["F020"]=False;reasons.pop("F020",None);coverage_present["F020"]+=1
            else:
                vals["F020"]=None;miss["F020"]=True;reasons["F020"]="UNIQUE_NATIVE_1D_ATR_NOT_AVAILABLE";coverage_missing["F020"]+=1

            # Certified reference price.
            ref=to_float(get_path(rrw,REFERENCE_PRICE_PATH))
            if ref is None or ref<=0:
                raise RepairError(f"{symbol} {d}: certified reference price unavailable")
            # Daily close should match as-of native 1d close if daily bar exists on/before as_of.
            _,daily_close=prefix_close_on_or_before(hist,d)
            if daily_close is not None:
                if abs(daily_close-ref) > 1e-9*max(1.0,abs(ref),abs(daily_close)):
                    reference_mismatch_count+=1

            if atr is not None:
                vals["F021"]=atr/ref;miss["F021"]=False;reasons.pop("F021",None);coverage_present["F021"]+=1
            else:
                vals["F021"]=None;miss["F021"]=True;reasons["F021"]="ATR_UNAVAILABLE";coverage_missing["F021"]+=1

            for fid,key in (("F030","support_levels"),("F031","resistance_levels")):
                v=nearest_distance(p.get(key),ref)
                if v is not None:
                    vals[fid]=v;miss[fid]=False;reasons.pop(fid,None);coverage_present[fid]+=1
                else:
                    vals[fid]=None;miss[fid]=True;reasons[fid]="NO_STRUCTURAL_LEVEL_AVAILABLE";coverage_missing[fid]+=1

            rs=relative_strength(hist,spy_hist,d)
            if rs is not None and (rs.get("rs_13w") is not None or rs.get("rs_26w") is not None):
                vals["F070"]=rs;miss["F070"]=False;reasons.pop("F070",None);coverage_present["F070"]+=1
            else:
                vals["F070"]=None;miss["F070"]=True;reasons["F070"]="INSUFFICIENT_SYMBOL_OR_SPY_TRAILING_SESSIONS";coverage_missing["F070"]+=1

            loc=trailing_52w_location(hist,d)
            for fid in ("F080","F081"):
                v=loc.get(fid)
                if v is not None:
                    vals[fid]=v;miss[fid]=False;reasons.pop(fid,None);coverage_present[fid]+=1
                else:
                    vals[fid]=None;miss[fid]=True;reasons[fid]="INSUFFICIENT_FROZEN_DAILY_PREFIX";coverage_missing[fid]+=1

            # Preserve governed non-materialization.
            for fid,reason in (
                ("F012","SCHEMA_CENSUS_ONLY_FIELD_WHITELIST_NOT_YET_FROZEN"),
                ("F051","SCHEMA_CENSUS_ONLY_FIELD_WHITELIST_NOT_YET_FROZEN"),
                ("F071","PIT_SECTOR_AUTHORITY_NOT_AVAILABLE"),
            ):
                vals[fid]=None;miss[fid]=True;reasons[fid]=reason

            row["feature_values"]=vals
            row["feature_missing"]=miss
            row["feature_missing_reason"]=reasons
            row["m77_19_8_4_3_certified_backfill"]=True
            row["reference_price_source"]=REFERENCE_PRICE_PATH
            row["daily_source_sha256"]=sha256_file(df)
            out_rows.append(row)

        out=outroot/f"{symbol}.jsonl.gz"
        write_jsonl_gz(out,out_rows)
        symbols.append({
            "symbol":symbol,
            "row_count":len(out_rows),
            "output_file":str(out.relative_to(root)),
            "output_sha256":sha256_file(out),
            "daily_source_file":str(df.relative_to(root)),
            "daily_source_sha256":sha256_file(df),
        })
        total_rows+=len(out_rows)

    if total_rows!=args.expected_matrix_row_count:
        raise RepairError(f"Development row count changed: {total_rows}")
    if len(symbols)!=args.expected_matrix_symbol_count:
        raise RepairError(f"active partition symbol count changed: {len(symbols)}")
    if args.active_partition_label=="DEVELOPMENT":
        if validation_rows_materialized or final_holdout_rows_materialized:
            raise RepairError("non-Development rows materialized")
    elif args.active_partition_label=="VALIDATION":
        if final_holdout_rows_materialized:
            raise RepairError("Final Holdout rows materialized during Validation")
    elif args.active_partition_label=="FINAL_HOLDOUT":
        if validation_rows_materialized:
            raise RepairError("Validation rows materialized during Final Holdout")

    summary=[]
    for fid in BACKFILL_FEATURES:
        total=coverage_present[fid]+coverage_missing[fid]
        summary.append({
            "feature_id":fid,
            "present_count":coverage_present[fid],
            "missing_count":coverage_missing[fid],
            "coverage_pct":None if total==0 else coverage_present[fid]/total,
        })

    report={
        "version":VERSION,
        "status":"READY",
        "resolver_authority_sha256":sha256_file(rp),
        "upstream_84_authority_sha256":sha256_file(bp),
        "development_end":DEV_END,
        "materialized_symbol_count":len(symbols),
        "materialized_row_count":total_rows,
        "reference_price_source":REFERENCE_PRICE_PATH,
        "daily_date_field":DATE_FIELD,
        "daily_close_field":CLOSE_FIELD,
        "reference_price_vs_daily_close_mismatch_count":reference_mismatch_count,
        "backfilled_feature_ids":BACKFILL_FEATURES,
        "census_only_feature_ids":CENSUS_ONLY_FEATURES,
        "still_blocked_feature_ids":STILL_BLOCKED_FEATURES,
        "coverage_summary":summary,
        "symbols":symbols,
        "governance":{
            "development_only":True,
            "source_contracts_certified_by_8_4_2":True,
            "feature_semantics_changed":False,
            "outcome_or_target_file_opened":False,
            "target_matrix_materialized":False,
            "validation_feature_rows_materialized":False,
            "final_holdout_feature_rows_materialized":False,
            "F012_flattened":False,
            "F051_flattened":False,
            "F071_materialized":False,
            "blocked_features_approximated":False,
            "future_information_used_for_features":False,
            "standardization_fit":False,
            "imputation_fit":False,
            "feature_selection_performed":False,
            "model_training_performed":False,
            "model_scoring_performed":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"REVIEW_M77_19_8_4_3_BACKFILL_COVERAGE_THEN_BUILD_M77_19_8_5_STRUCTURED_FEATURE_FIELD_WHITELIST_AND_DEVELOPMENT_TARGET_MATRIX_AUTHORITY",
    }

    oj=resolve(root,args.output_json);oc=resolve(root,args.output_csv)
    atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=["feature_id","present_count","missing_count","coverage_pct"])
        w.writeheader();w.writerows(summary)

    print("=== M77.19.8.4.3 CERTIFIED SOURCE RESOLVER DEVELOPMENT FEATURE BACKFILL REPAIR ===")
    print("status: READY")
    print("development_end:",DEV_END)
    print("materialized_symbol_count:",len(symbols))
    print("materialized_row_count:",total_rows)
    print("reference_price_source:",REFERENCE_PRICE_PATH)
    print("daily_date_field:",DATE_FIELD)
    print("daily_close_field:",CLOSE_FIELD)
    print("reference_price_vs_daily_close_mismatch_count:",reference_mismatch_count)
    for row in summary:
        print(f"{row['feature_id']}: present={row['present_count']} missing={row['missing_count']} coverage_pct={row['coverage_pct']}")
    print("F012_flattened: False")
    print("F051_flattened: False")
    print("F071_materialized: False")
    print("outcome_or_target_file_opened: False")
    print("target_matrix_materialized: False")
    print("validation_feature_rows_materialized: False")
    print("final_holdout_feature_rows_materialized: False")
    print("model_training_performed: False")
    print("production_authority_effect: False")
    print("next_step: REVIEW_M77_19_8_4_3_BACKFILL_COVERAGE_THEN_BUILD_M77_19_8_5_STRUCTURED_FEATURE_FIELD_WHITELIST_AND_DEVELOPMENT_TARGET_MATRIX_AUTHORITY")
    print("report:",oj)
    print("csv:",oc)
    print("output_root:",outroot)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
