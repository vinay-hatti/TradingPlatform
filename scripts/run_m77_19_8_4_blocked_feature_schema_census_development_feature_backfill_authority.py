#!/usr/bin/env python3
"""
M77.19.8.4 — Blocked Feature Schema Census & Development Feature Backfill Authority

Development-only authority that:
1. performs schema census for structured F012 timeframe_states and
   F051 institutional_volume, but does NOT flatten them yet;
2. backfills only preregistered simple extractors:
   F020, F021, F030, F031, F070, F080, F081;
3. leaves F071 sector-relative strength blocked;
4. reads no outcome/target files;
5. materializes no Validation or Final Holdout feature rows;
6. trains/scores no model and changes no production authority.

The backfill rewrites the M77.19.8.2 Development matrix into a new M77.19.8.4
root rather than mutating the 8.2 authority in place.
"""
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, math, os, tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.8.4-BLOCKED-FEATURE-SCHEMA-CENSUS-DEVELOPMENT-FEATURE-BACKFILL-AUTHORITY-1.0"
EXPECTED_83_VERSION="M77.19.8.3-BLOCKED-FEATURE-EXTRACTOR-AUTHORITY-DEVELOPMENT-TARGET-MATRIX-PREREGISTRATION-1.0"
EXPECTED_82_VERSION="M77.19.8.2-DEVELOPMENT-ONLY-FEATURE-MATRIX-MATERIALIZATION-SCHEMA-VALIDATION-1.0"
EXPECTED_REPLAY_SHA="0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
DEV_END="2017-12-31"
VALIDATION_START="2018-01-01"
FINAL_HOLDOUT_START="2023-01-01"

BACKFILL_FEATURES=["F020","F021","F030","F031","F070","F080","F081"]
CENSUS_ONLY_FEATURES=["F012","F051"]
STILL_BLOCKED_FEATURES=["F071"]

class BackfillError(RuntimeError): pass

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
            if not line.strip():continue
            try: yield json.loads(line)
            except Exception as exc: raise BackfillError(f"{path}:{i}: invalid JSONL") from exc

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def write_jsonl_gz(path:Path,rows:Iterable[Mapping[str,Any]]):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with gzip.open(tmp,"wt",encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def to_float(v):
    if v is None or isinstance(v,bool): return None
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None

def scalar_leaf_paths(obj:Any,prefix:str="")->dict[str,str]:
    """Return leaf path -> type name; arrays/objects are structural, not model fields."""
    out={}
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v,dict):
                out.update(scalar_leaf_paths(v,p))
            elif isinstance(v,list):
                out[p]="list"
            elif v is None:
                out[p]="null"
            elif isinstance(v,bool):
                out[p]="bool"
            elif isinstance(v,(int,float)):
                out[p]="number"
            elif isinstance(v,str):
                out[p]="string"
            else:
                out[p]=type(v).__name__
    return out

def find_numeric_by_key_fragment(obj:Any, fragments:list[str]):
    """Fail-soft extractor over same-as-of native payload; no future data."""
    hits=[]
    def walk(x,path=""):
        if isinstance(x,dict):
            for k,v in x.items():
                p=f"{path}.{k}" if path else str(k)
                kl=str(k).lower()
                if all(f in kl for f in fragments):
                    fv=to_float(v)
                    if fv is not None: hits.append((p,fv))
                walk(v,p)
        elif isinstance(x,list):
            for j,v in enumerate(x): walk(v,f"{path}[{j}]")
    walk(obj)
    if len(hits)==1:return hits[0]
    return None

def get_reference_price(row:Mapping[str,Any], profile:Mapping[str,Any]):
    # Use only explicit same-as-of price-like scalar present in replay/profile.
    candidates=[]
    keys=("reference_price","current_price","close","price","underlying_price")
    for container_name,container in (("row",row),("profile",profile),("context",profile.get("context") or {})):
        if isinstance(container,dict):
            for k in keys:
                if k in container:
                    v=to_float(container.get(k))
                    if v is not None and v>0:candidates.append((f"{container_name}.{k}",v))
    # deterministic priority by keys/container insertion above; reject conflicting values > 1bp.
    if not candidates:return None,None
    base=candidates[0][1]
    if any(abs(v-base)/base>0.0001 for _,v in candidates[1:]):
        return None,"AMBIGUOUS_REFERENCE_PRICE"
    return base,candidates[0][0]

def extract_level_price(level:Any):
    if isinstance(level,(int,float)):return to_float(level)
    if not isinstance(level,dict):return None
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

def load_daily_history(path:Path):
    """Support M77.19.7.2 JSONL.GZ or JSON.GZ-like daily artifacts conservatively."""
    rows=[]
    if not path.exists():return rows
    if path.suffix==".gz":
        with gzip.open(path,"rt",encoding="utf-8") as fh:
            text=fh.read()
    else:
        text=path.read_text(encoding="utf-8")
    text=text.strip()
    if not text:return rows
    if text.startswith("["):
        obj=json.loads(text); raw=obj
    elif text.startswith("{"):
        obj=json.loads(text)
        raw=obj.get("rows") or obj.get("bars") or obj.get("results") or []
    else:
        raw=[json.loads(line) for line in text.splitlines() if line.strip()]
    for r in raw:
        if not isinstance(r,dict):continue
        d=str(r.get("date") or r.get("session_date") or r.get("as_of") or "")[:10]
        c=to_float(r.get("close") if "close" in r else r.get("c"))
        if d and c is not None and c>0: rows.append((d,c))
    rows.sort()
    return rows

def locate_daily_file(materialization_root:Path,symbol:str):
    candidates=[]
    patterns=[
        f"**/{symbol}.jsonl.gz", f"**/{symbol}.json.gz", f"**/{symbol}.jsonl",
        f"**/{symbol}.json", f"**/{symbol}_*.jsonl.gz", f"**/{symbol}_*.json.gz"
    ]
    for pat in patterns:
        candidates.extend(materialization_root.glob(pat))
    # Exclude metadata/report-like files where possible.
    candidates=[p for p in candidates if p.is_file() and "manifest" not in p.name.lower() and "summary" not in p.name.lower()]
    uniq=sorted(set(candidates))
    return uniq[0] if len(uniq)==1 else None

def trailing_features(history:list[tuple[str,float]],as_of:str,spy_hist:list[tuple[str,float]]):
    sym=[(d,c) for d,c in history if d<=as_of]
    spy=[(d,c) for d,c in spy_hist if d<=as_of]
    if not sym:return {}
    current=sym[-1][1]
    last252=sym[-252:]
    out={}
    if len(last252)>=2:
        peak=max(c for _,c in last252);low=min(c for _,c in last252)
        out["F080"]=current/peak-1 if peak else None
        out["F081"]=current/low-1 if low else None
    # F070 preregistered as two scalars later, but F070 is one frozen feature ID.
    # Preserve a structured two-value object in the research matrix; it is NOT
    # authorized for direct model input until a later field-level expansion.
    if spy:
        def ret_at(n):
            if len(sym)<n+1 or len(spy)<n+1:return None
            return sym[-1][1]/sym[-1-n][1]-1, spy[-1][1]/spy[-1-n][1]-1
        r13=ret_at(65);r26=ret_at(130)
        if r13 or r26:
            out["F070"]={
                "rs_13w":None if r13 is None else r13[0]-r13[1],
                "rs_26w":None if r26 is None else r26[0]-r26[1],
            }
    return out

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--extractor-authority-json",default="reports/m77_19_8_3_blocked_feature_extractor_authority_development_target_matrix_preregistration.json")
    ap.add_argument("--matrix-authority-json",default="reports/m77_19_8_2_development_only_feature_matrix_materialization_schema_validation.json")
    ap.add_argument("--matrix-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-root",default="research_data/m77_19_8_4/development_feature_matrix_backfilled")
    ap.add_argument("--output-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_4_schema_census_and_backfill_summary.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    ep=resolve(root,args.extractor_authority_json)
    mp=resolve(root,args.matrix_authority_json)
    mr=resolve(root,args.matrix_root)
    rr=resolve(root,args.replay_root)
    dr=resolve(root,args.daily_materialization_root)
    outroot=resolve(root,args.output_root)

    ea=load_json(ep);ma=load_json(mp)
    if ea.get("version")!=EXPECTED_83_VERSION or ea.get("status")!="READY":
        raise BackfillError("M77.19.8.3 authority invalid")
    if ma.get("version")!=EXPECTED_82_VERSION or ma.get("status")!="READY":
        raise BackfillError("M77.19.8.2 authority invalid")
    if ma.get("materialized_row_count")!=303689 or ma.get("materialized_symbol_count")!=524:
        raise BackfillError("M77.19.8.2 row/symbol authority mismatch")
    if ea.get("research_governance",{}).get("outcome_or_target_file_opened") is not False:
        raise BackfillError("8.3 target-read governance invalid")

    matrix_files=sorted(mr.glob("*.jsonl.gz"))
    if len(matrix_files)!=524:raise BackfillError(f"expected 524 matrix files, found {len(matrix_files)}")
    replay_files={p.name[:-9]:p for p in (rr/"weekly"/"profiles").glob("*.jsonl.gz")}
    if len(replay_files)!=602:raise BackfillError("expected 602 replay files")

    # Locate SPY frozen daily history; if unavailable, F070 stays missing, never approximated.
    spy_file=locate_daily_file(dr,"SPY")
    spy_hist=load_daily_history(spy_file) if spy_file else []

    census={"F012":Counter(),"F051":Counter()}
    census_type_conflicts={"F012":defaultdict(set),"F051":defaultdict(set)}
    present=Counter();missing=Counter();reason_counts=Counter()
    symbol_summaries=[];total_rows=0
    validation_rows_materialized=0;final_holdout_rows_materialized=0

    for mf in matrix_files:
        symbol=mf.name[:-9]
        rf=replay_files.get(symbol)
        if rf is None:raise BackfillError(f"{symbol}: replay file missing")
        replay_by_date={}
        for r in iter_jsonl_gz(rf):
            d=str(r.get("as_of") or "")[:10]
            if d<=DEV_END and r.get("status")=="REPLAYED":
                replay_by_date[d]=r

        daily_file=locate_daily_file(dr,symbol)
        hist=load_daily_history(daily_file) if daily_file else []
        out_rows=[]
        for row in iter_jsonl_gz(mf):
            d=str(row.get("as_of") or "")[:10]
            if d>=FINAL_HOLDOUT_START:
                final_holdout_rows_materialized+=1;continue
            if d>=VALIDATION_START:
                validation_rows_materialized+=1;continue
            rrw=replay_by_date.get(d)
            if rrw is None:raise BackfillError(f"{symbol} {d}: Development replay provenance missing")
            p=rrw.get("profile") or {}
            if not isinstance(p,dict):raise BackfillError(f"{symbol} {d}: full profile missing")

            # Census only; no field extraction into feature values.
            for fid,payload in (("F012",p.get("timeframe_states")),("F051",p.get("institutional_volume"))):
                for path,t in scalar_leaf_paths(payload).items():
                    census[fid][path]+=1
                    census_type_conflicts[fid][path].add(t)

            vals=dict(row.get("feature_values") or {})
            miss=dict(row.get("feature_missing") or {})
            reasons=dict(row.get("feature_missing_reason") or {})

            # F020 exact native 1d ATR scalar, only if uniquely discoverable by ATR key.
            ts=p.get("timeframe_states") or {}
            one=ts.get("1d") if isinstance(ts,dict) else None
            atr_hit=find_numeric_by_key_fragment(one,["atr"]) if isinstance(one,dict) else None
            if atr_hit:
                vals["F020"]=atr_hit[1];miss["F020"]=False;reasons.pop("F020",None);present["F020"]+=1
            else:
                vals["F020"]=None;miss["F020"]=True;reasons["F020"]="UNIQUE_NATIVE_1D_ATR_NOT_AVAILABLE";missing["F020"]+=1

            ref,refsrc=get_reference_price(rrw,p)
            if vals.get("F020") is not None and ref:
                vals["F021"]=float(vals["F020"])/ref;miss["F021"]=False;reasons.pop("F021",None);present["F021"]+=1
            else:
                vals["F021"]=None;miss["F021"]=True;reasons["F021"]="ATR_OR_REFERENCE_PRICE_UNAVAILABLE";missing["F021"]+=1

            for fid,key in (("F030","support_levels"),("F031","resistance_levels")):
                v=nearest_distance(p.get(key),ref) if ref else None
                if v is not None:
                    vals[fid]=v;miss[fid]=False;reasons.pop(fid,None);present[fid]+=1
                else:
                    vals[fid]=None;miss[fid]=True;reasons[fid]="REFERENCE_PRICE_OR_LEVEL_UNAVAILABLE";missing[fid]+=1

            tr=trailing_features(hist,d,spy_hist)
            for fid in ("F070","F080","F081"):
                v=tr.get(fid)
                if v is not None:
                    vals[fid]=v;miss[fid]=False;reasons.pop(fid,None);present[fid]+=1
                else:
                    vals[fid]=None;miss[fid]=True
                    reasons[fid]="FROZEN_DAILY_PREFIX_OR_SPY_HISTORY_UNAVAILABLE" if fid=="F070" else "FROZEN_DAILY_PREFIX_52W_WINDOW_UNAVAILABLE"
                    missing[fid]+=1

            # F012/F051 census only, F071 still blocked.
            for fid,reason in (
                ("F012","SCHEMA_CENSUS_ONLY_FIELD_WHITELIST_NOT_YET_FROZEN"),
                ("F051","SCHEMA_CENSUS_ONLY_FIELD_WHITELIST_NOT_YET_FROZEN"),
                ("F071","PIT_SECTOR_AUTHORITY_NOT_AVAILABLE"),
            ):
                vals[fid]=None;miss[fid]=True;reasons[fid]=reason;missing[fid]+=1

            row["feature_values"]=vals
            row["feature_missing"]=miss
            row["feature_missing_reason"]=reasons
            row["m77_19_8_4_backfilled"]=True
            out_rows.append(row)

        out=outroot/f"{symbol}.jsonl.gz"
        write_jsonl_gz(out,out_rows)
        symbol_summaries.append({
            "symbol":symbol,"row_count":len(out_rows),
            "output_file":str(out.relative_to(root)),
            "output_sha256":sha256_file(out),
            "daily_source_file":None if daily_file is None else str(daily_file.relative_to(root)),
            "daily_source_sha256":None if daily_file is None else sha256_file(daily_file),
        })
        total_rows+=len(out_rows)

    if validation_rows_materialized or final_holdout_rows_materialized:
        raise BackfillError("non-Development rows encountered in Development matrix")

    census_summary={}
    for fid in CENSUS_ONLY_FEATURES:
        census_summary[fid]={
            "distinct_scalar_leaf_path_count":len(census[fid]),
            "scalar_leaf_paths":[
                {"path":p,"observation_count":census[fid][p],"observed_types":sorted(census_type_conflicts[fid][p])}
                for p in sorted(census[fid])
            ],
            "field_whitelist_frozen":False,
            "materialized_into_model_feature":False,
        }

    summary_rows=[]
    for fid in BACKFILL_FEATURES+CENSUS_ONLY_FEATURES+STILL_BLOCKED_FEATURES:
        state=("BACKFILLED_WHERE_AVAILABLE" if fid in BACKFILL_FEATURES
               else "SCHEMA_CENSUS_ONLY" if fid in CENSUS_ONLY_FEATURES
               else "BLOCKED")
        summary_rows.append({
            "feature_id":fid,"state":state,
            "present_count":present[fid],"missing_count":missing[fid],
            "census_leaf_path_count":len(census.get(fid,{})),
        })

    report={
        "version":VERSION,"status":"READY",
        "extractor_authority_sha256":sha256_file(ep),
        "matrix_authority_sha256":sha256_file(mp),
        "development_end":DEV_END,
        "materialized_symbol_count":len(symbol_summaries),
        "materialized_row_count":total_rows,
        "backfilled_feature_ids":BACKFILL_FEATURES,
        "census_only_feature_ids":CENSUS_ONLY_FEATURES,
        "still_blocked_feature_ids":STILL_BLOCKED_FEATURES,
        "schema_census":census_summary,
        "backfill_summary":summary_rows,
        "symbols":symbol_summaries,
        "spy_daily_source_file":None if spy_file is None else str(spy_file.relative_to(root)),
        "spy_daily_source_sha256":None if spy_file is None else sha256_file(spy_file),
        "governance":{
            "development_only":True,
            "outcome_or_target_file_opened":False,
            "target_matrix_materialized":False,
            "validation_feature_rows_materialized":False,
            "final_holdout_feature_rows_materialized":False,
            "F012_flattened":False,
            "F051_flattened":False,
            "F071_materialized":False,
            "blocked_or_missing_features_approximated":False,
            "future_information_used_for_features":False,
            "standardization_fit":False,
            "imputation_fit":False,
            "feature_selection_performed":False,
            "model_training_performed":False,
            "model_scoring_performed":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_8_5_STRUCTURED_FEATURE_FIELD_WHITELIST_AND_DEVELOPMENT_TARGET_MATRIX_AUTHORITY",
    }

    oj=resolve(root,args.output_json);oc=resolve(root,args.output_csv)
    atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(summary_rows[0].keys()))
        w.writeheader();w.writerows(summary_rows)

    print("=== M77.19.8.4 BLOCKED FEATURE SCHEMA CENSUS & DEVELOPMENT FEATURE BACKFILL AUTHORITY ===")
    print("status: READY")
    print("development_end:",DEV_END)
    print("materialized_symbol_count:",len(symbol_summaries))
    print("materialized_row_count:",total_rows)
    print("backfilled_feature_ids:",BACKFILL_FEATURES)
    print("census_only_feature_ids:",CENSUS_ONLY_FEATURES)
    print("still_blocked_feature_ids:",STILL_BLOCKED_FEATURES)
    print("F012_scalar_leaf_path_count:",len(census["F012"]))
    print("F051_scalar_leaf_path_count:",len(census["F051"]))
    for fid in BACKFILL_FEATURES:
        print(f"{fid}: present={present[fid]} missing={missing[fid]}")
    print("outcome_or_target_file_opened: False")
    print("target_matrix_materialized: False")
    print("validation_feature_rows_materialized: False")
    print("final_holdout_feature_rows_materialized: False")
    print("F012_flattened: False")
    print("F051_flattened: False")
    print("F071_materialized: False")
    print("model_training_performed: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_5_STRUCTURED_FEATURE_FIELD_WHITELIST_AND_DEVELOPMENT_TARGET_MATRIX_AUTHORITY")
    print("report:",oj)
    print("csv:",oc)
    print("output_root:",outroot)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
