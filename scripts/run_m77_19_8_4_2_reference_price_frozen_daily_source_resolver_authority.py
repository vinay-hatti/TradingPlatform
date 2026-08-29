#!/usr/bin/env python3
"""
M77.19.8.4.2 — Reference Price & Frozen Daily Source Resolver Authority

Certifies:
1) a single same-as-of native reference-price path only after exact cross-path
   consistency analysis on Development replay rows; and
2) the actual M77.19.7.2 frozen daily source resolver for *.daily.csv.gz files,
   including exact date/close field discovery.

No feature matrix is mutated.
No outcomes/targets are read.
Validation and Final Holdout remain closed.
No models are trained/scored.
"""
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, math, os, tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

VERSION="M77.19.8.4.2-REFERENCE-PRICE-FROZEN-DAILY-SOURCE-RESOLVER-AUTHORITY-1.0"
EXPECTED_841_VERSION="M77.19.8.4.1-BACKFILL-SOURCE-RESOLUTION-REFERENCE-PRICE-FORENSICS-1.0"
DEV_END="2017-12-31"
REFERENCE_CANDIDATE_PATHS=[
    "profile.decision_intelligence.explainability.opportunity_freshness.reference_price",
    "profile.timeframe_states.1d.close",
    "profile.trade_plan.certification.entry_execution.reference_price",
    "profile.trade_plan.certification.reference_market.price",
    "profile.trade_plan.geometry_context.reference_price",
    "profile.trade_plan.reference_market.price",
]
PREFERRED_REFERENCE_PATH="profile.timeframe_states.1d.close"

class ResolverError(RuntimeError): pass

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
            except Exception as exc: raise ResolverError(f"{path}:{i}: invalid JSONL") from exc

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
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
    if v is None or isinstance(v,bool):return None
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:return None

def compare_values(a,b,tol=1e-12):
    if a is None or b is None:return None
    return abs(a-b) <= tol*max(1.0,abs(a),abs(b))

def inspect_daily_csv(path:Path):
    opener=gzip.open if path.suffix==".gz" else open
    with opener(path,"rt",encoding="utf-8",newline="") as fh:
        reader=csv.DictReader(fh)
        fieldnames=reader.fieldnames or []
        rows=[]
        for i,r in enumerate(reader):
            rows.append(r)
            if i>=19:break
    date_candidates=[]
    close_candidates=[]
    for f in fieldnames:
        fl=f.lower()
        if fl in ("date","session_date","as_of","timestamp","time") or "date" in fl:
            date_candidates.append(f)
        if fl in ("close","c","adj_close","adjusted_close") or fl.endswith("_close"):
            close_candidates.append(f)
    return {
        "fieldnames":fieldnames,
        "sample_row_count":len(rows),
        "date_candidates":date_candidates,
        "close_candidates":close_candidates,
        "sample_rows":rows[:3],
    }

def exact_daily_file_map(root:Path):
    files=sorted(root.rglob("*.daily.csv.gz"))
    mapping=defaultdict(list)
    for p in files:
        name=p.name
        symbol=name[:-len(".daily.csv.gz")]
        mapping[symbol].append(p)
    return files,mapping

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--forensics-json",default="reports/m77_19_8_4_1_backfill_source_resolution_reference_price_forensics.json")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--max-reference-rows-per-symbol",type=int,default=100)
    ap.add_argument("--output-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_4_2_daily_source_resolver_registry.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    fp=resolve(root,args.forensics_json)
    rr=resolve(root,args.replay_root)
    dr=resolve(root,args.daily_materialization_root)
    f=load_json(fp)
    if f.get("version")!=EXPECTED_841_VERSION or f.get("status")!="READY":
        raise ResolverError("M77.19.8.4.1 forensics authority invalid")
    if f.get("forensic_conclusion")!="ZERO_COVERAGE_IS_SOURCE_RESOLUTION_NOT_FEATURE_EVIDENCE":
        raise ResolverError("unexpected 8.4.1 conclusion")

    replay_files=sorted((rr/"weekly"/"profiles").glob("*.jsonl.gz"))
    if len(replay_files)!=602:
        raise ResolverError(f"expected 602 replay files, found {len(replay_files)}")

    pair_stats={}
    for a in REFERENCE_CANDIDATE_PATHS:
        for b in REFERENCE_CANDIDATE_PATHS:
            if a>=b:continue
            pair_stats[(a,b)]={"compared":0,"exact":0,"mismatch":0,"max_abs_diff":0.0}
    path_present=Counter()
    rows_examined=0
    symbols_examined=0

    for rf in replay_files:
        n=0;had=False
        for row in iter_jsonl_gz(rf):
            d=str(row.get("as_of") or "")[:10]
            if d>DEV_END or row.get("status")!="REPLAYED":continue
            vals={p:to_float(get_path(row,p)) for p in REFERENCE_CANDIDATE_PATHS}
            rows_examined+=1;n+=1;had=True
            for p,v in vals.items():
                if v is not None:path_present[p]+=1
            for (a,b),s in pair_stats.items():
                va,vb=vals[a],vals[b]
                if va is None or vb is None:continue
                s["compared"]+=1
                diff=abs(va-vb)
                s["max_abs_diff"]=max(s["max_abs_diff"],diff)
                if compare_values(va,vb):
                    s["exact"]+=1
                else:
                    s["mismatch"]+=1
            if n>=args.max_reference_rows_per_symbol:break
        if had:symbols_examined+=1

    preferred_present=path_present[PREFERRED_REFERENCE_PATH]
    if preferred_present!=rows_examined:
        raise ResolverError(f"preferred reference path coverage incomplete: {preferred_present}/{rows_examined}")

    preferred_pair_results=[]
    for p in REFERENCE_CANDIDATE_PATHS:
        if p==PREFERRED_REFERENCE_PATH:continue
        a,b=sorted((PREFERRED_REFERENCE_PATH,p))
        s=pair_stats[(a,b)]
        preferred_pair_results.append({"other_path":p,**s})

    full_coverage_paths=[p for p in REFERENCE_CANDIDATE_PATHS if path_present[p]==rows_examined]
    all_full_paths_exact_to_preferred=True
    for p in full_coverage_paths:
        if p==PREFERRED_REFERENCE_PATH:continue
        a,b=sorted((PREFERRED_REFERENCE_PATH,p))
        s=pair_stats[(a,b)]
        if s["compared"]!=rows_examined or s["mismatch"]!=0:
            all_full_paths_exact_to_preferred=False

    if not all_full_paths_exact_to_preferred:
        raise ResolverError("broad reference-price paths are not exactly consistent with preferred native 1d close")

    daily_files,daily_map=exact_daily_file_map(dr)
    if len(daily_files)!=602:
        raise ResolverError(f"expected 602 *.daily.csv.gz files, found {len(daily_files)}")

    ambiguous={s:[str(p.relative_to(dr)) for p in ps] for s,ps in daily_map.items() if len(ps)!=1}
    if ambiguous:
        raise ResolverError(f"ambiguous daily source mappings detected: {list(ambiguous)[:10]}")

    # Match against replay universe.
    replay_symbols={p.name[:-9] for p in replay_files}
    daily_symbols=set(daily_map)
    missing_daily=sorted(replay_symbols-daily_symbols)
    extra_daily=sorted(daily_symbols-replay_symbols)
    if missing_daily:
        raise ResolverError(f"missing daily sources for replay symbols: {missing_daily[:20]}")

    schema_counts=Counter()
    schema_examples={}
    date_field_counts=Counter()
    close_field_counts=Counter()
    registry_rows=[]
    for symbol in sorted(replay_symbols):
        p=daily_map[symbol][0]
        info=inspect_daily_csv(p)
        schema_key="|".join(info["fieldnames"])
        schema_counts[schema_key]+=1
        schema_examples.setdefault(schema_key,info["fieldnames"])
        for d in info["date_candidates"]:date_field_counts[d]+=1
        for c in info["close_candidates"]:close_field_counts[c]+=1
        registry_rows.append({
            "symbol":symbol,
            "relative_path":str(p.relative_to(root)),
            "sha256":sha256_file(p),
            "fieldnames":"|".join(info["fieldnames"]),
            "date_candidates":"|".join(info["date_candidates"]),
            "close_candidates":"|".join(info["close_candidates"]),
        })

    if len(schema_counts)!=1:
        raise ResolverError(f"daily CSV schema is not uniform: {dict(schema_counts)}")
    fieldnames=next(iter(schema_examples.values()))
    date_candidates=[k for k,v in date_field_counts.items() if v==len(replay_symbols)]
    close_candidates=[k for k,v in close_field_counts.items() if v==len(replay_symbols)]
    if len(date_candidates)!=1 or len(close_candidates)!=1:
        raise ResolverError(f"cannot certify unique universal date/close fields: date={date_candidates} close={close_candidates}")

    date_field=date_candidates[0]
    close_field=close_candidates[0]

    report={
        "version":VERSION,
        "status":"READY",
        "forensics_authority_sha256":sha256_file(fp),
        "reference_price_authority":{
            "symbols_examined":symbols_examined,
            "rows_examined":rows_examined,
            "candidate_paths":REFERENCE_CANDIDATE_PATHS,
            "path_present_counts":dict(path_present),
            "full_coverage_paths":full_coverage_paths,
            "preferred_path":PREFERRED_REFERENCE_PATH,
            "preferred_path_present_count":preferred_present,
            "all_full_coverage_paths_exact_to_preferred":all_full_paths_exact_to_preferred,
            "preferred_pair_results":preferred_pair_results,
            "certified":True,
            "semantic":"SAME_AS_OF_NATIVE_1D_CLOSE",
        },
        "frozen_daily_source_resolver":{
            "file_glob":"**/*.daily.csv.gz",
            "expected_symbol_file_count":602,
            "resolved_symbol_file_count":len(replay_symbols),
            "unique_mapping_per_symbol":True,
            "filename_rule":"<symbol>.daily.csv.gz",
            "uniform_schema":True,
            "fieldnames":fieldnames,
            "date_field":date_field,
            "close_field":close_field,
            "missing_replay_symbols":missing_daily,
            "extra_daily_symbols":extra_daily,
            "certified":True,
        },
        "governance":{
            "feature_matrix_mutated":False,
            "feature_semantics_changed":False,
            "outcome_or_target_file_opened":False,
            "validation_data_opened":False,
            "final_holdout_data_opened":False,
            "model_training_performed":False,
            "model_scoring_performed":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_8_4_3_CERTIFIED_SOURCE_RESOLVER_DEVELOPMENT_FEATURE_BACKFILL_REPAIR",
    }

    oj=resolve(root,args.output_json);oc=resolve(root,args.output_csv)
    atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(registry_rows[0].keys()))
        w.writeheader();w.writerows(registry_rows)

    print("=== M77.19.8.4.2 REFERENCE PRICE & FROZEN DAILY SOURCE RESOLVER AUTHORITY ===")
    print("status: READY")
    print("reference_price_rows_examined:",rows_examined)
    print("reference_price_full_coverage_paths:",full_coverage_paths)
    print("reference_price_preferred_path:",PREFERRED_REFERENCE_PATH)
    print("all_full_coverage_paths_exact_to_preferred:",all_full_paths_exact_to_preferred)
    print("reference_price_certified: True")
    print("daily_file_glob: **/*.daily.csv.gz")
    print("daily_resolved_symbol_file_count:",len(replay_symbols))
    print("daily_unique_mapping_per_symbol: True")
    print("daily_uniform_schema: True")
    print("daily_date_field:",date_field)
    print("daily_close_field:",close_field)
    print("daily_resolver_certified: True")
    print("feature_matrix_mutated: False")
    print("outcome_or_target_file_opened: False")
    print("validation_data_opened: False")
    print("final_holdout_data_opened: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_4_3_CERTIFIED_SOURCE_RESOLVER_DEVELOPMENT_FEATURE_BACKFILL_REPAIR")
    print("report:",oj)
    print("csv:",oc)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
