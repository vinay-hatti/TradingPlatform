#!/usr/bin/env python3
"""
M77.19.8.4.1 — Backfill Source-Resolution & Reference-Price Forensics

Diagnoses the zero-coverage result from M77.19.8.4 for:
F021, F030, F031, F070, F080, F081.

This milestone is forensic/report-only:
- no feature matrix mutation;
- no feature semantic change;
- no target/outcome reads;
- no Validation/Final Holdout materialization;
- no training/scoring;
- no production effect.

It inspects only Development replay rows and frozen M77.19.7.2 materialization
file layout/schema to determine:
1) where a same-as-of reference price is actually exposed;
2) how frozen daily source artifacts are named and structured;
3) whether a deterministic source resolver can be certified next.
"""
from __future__ import annotations

import argparse, gzip, hashlib, json, os, tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

VERSION="M77.19.8.4.1-BACKFILL-SOURCE-RESOLUTION-REFERENCE-PRICE-FORENSICS-1.0"
EXPECTED_84_VERSION="M77.19.8.4-BLOCKED-FEATURE-SCHEMA-CENSUS-DEVELOPMENT-FEATURE-BACKFILL-AUTHORITY-1.0"
DEV_END="2017-12-31"

class ForensicError(RuntimeError): pass

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
            except Exception as exc: raise ForensicError(f"{path}:{i}: invalid JSONL") from exc

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def scalar_leafs(obj:Any,prefix:str="")->list[tuple[str,Any]]:
    out=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v,dict):
                out.extend(scalar_leafs(v,p))
            elif isinstance(v,list):
                continue
            else:
                out.append((p,v))
    return out

def price_like_candidates(row:dict[str,Any])->list[dict[str,Any]]:
    keys=("price","close","reference","underlying","spot","last")
    out=[]
    for path,v in scalar_leafs(row):
        pl=path.lower()
        if not any(k in pl for k in keys): continue
        if isinstance(v,bool) or v is None: continue
        try:
            x=float(v)
        except Exception:
            continue
        if x<=0: continue
        out.append({"path":path,"value":x})
    return out

def inspect_file(path:Path)->dict[str,Any]:
    info={
        "path":str(path),
        "suffixes":path.suffixes,
        "size_bytes":path.stat().st_size,
        "sha256":sha256_file(path),
        "parse_mode":None,
        "top_level_type":None,
        "sample_keys":[],
        "row_count_observed":0,
        "date_key_candidates":Counter(),
        "close_key_candidates":Counter(),
        "error":None,
    }
    try:
        if path.suffix==".gz":
            with gzip.open(path,"rt",encoding="utf-8") as fh:
                text=fh.read(2_000_000)
        else:
            text=path.read_text(encoding="utf-8")[:2_000_000]
        s=text.lstrip()
        rows=[]
        if not s:
            info["parse_mode"]="EMPTY"
            return info
        if s.startswith("["):
            obj=json.loads(s)
            info["parse_mode"]="JSON_ARRAY"
            info["top_level_type"]="list"
            rows=obj[:20] if isinstance(obj,list) else []
        elif s.startswith("{"):
            # Could be one JSON object or JSONL where first line is object.
            try:
                obj=json.loads(s)
                info["parse_mode"]="JSON_OBJECT"
                info["top_level_type"]="dict"
                if isinstance(obj,dict):
                    info["sample_keys"]=sorted(obj.keys())[:100]
                    for k in ("rows","bars","results","data"):
                        if isinstance(obj.get(k),list):
                            rows=obj[k][:20]
                            break
                    if not rows:
                        rows=[obj]
            except Exception:
                info["parse_mode"]="JSONL"
                rows=[]
                for line in s.splitlines()[:20]:
                    try: rows.append(json.loads(line))
                    except Exception: pass
        else:
            info["parse_mode"]="UNKNOWN_TEXT"
        info["row_count_observed"]=len(rows)
        for r in rows:
            if not isinstance(r,dict): continue
            if not info["sample_keys"]:
                info["sample_keys"]=sorted(r.keys())[:100]
            for k in r:
                kl=str(k).lower()
                if any(x in kl for x in ("date","session","timestamp","time","as_of")):
                    info["date_key_candidates"][k]+=1
                if kl in ("close","c","adj_close","adjusted_close") or "close" in kl:
                    info["close_key_candidates"][k]+=1
    except Exception as exc:
        info["error"]=f"{type(exc).__name__}: {exc}"
    info["date_key_candidates"]=dict(info["date_key_candidates"])
    info["close_key_candidates"]=dict(info["close_key_candidates"])
    return info

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--backfill-authority-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--max-replay-rows-per-symbol",type=int,default=25)
    ap.add_argument("--max-daily-files-to-inspect",type=int,default=200)
    ap.add_argument("--output-json",default="reports/m77_19_8_4_1_backfill_source_resolution_reference_price_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_4_1_daily_materialization_file_inventory.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    bp=resolve(root,args.backfill_authority_json)
    rr=resolve(root,args.replay_root)
    dr=resolve(root,args.daily_materialization_root)
    ba=load_json(bp)
    if ba.get("version")!=EXPECTED_84_VERSION or ba.get("status")!="READY":
        raise ForensicError("M77.19.8.4 authority invalid")
    summary={x["feature_id"]:x for x in ba.get("backfill_summary") or []}
    expected_zero=("F021","F030","F031","F070","F080","F081")
    for fid in expected_zero:
        if int(summary.get(fid,{}).get("present_count",-1))!=0:
            raise ForensicError(f"{fid}: upstream zero-coverage authority changed")

    replay_files=sorted((rr/"weekly"/"profiles").glob("*.jsonl.gz"))
    if len(replay_files)!=602:
        raise ForensicError(f"expected 602 replay files, found {len(replay_files)}")

    # Reference-price census on Development REPLAYED rows.
    path_counts=Counter()
    path_symbol_counts=defaultdict(set)
    path_value_examples=defaultdict(list)
    rows_examined=0
    symbols_examined=0
    rows_with_any_price_like=0
    per_symbol_price_path_sets={}
    for rf in replay_files:
        symbol=rf.name[:-9]
        n=0
        sym_paths=set()
        for row in iter_jsonl_gz(rf):
            d=str(row.get("as_of") or "")[:10]
            if d>DEV_END or row.get("status")!="REPLAYED": continue
            cands=price_like_candidates(row)
            rows_examined+=1
            n+=1
            if cands: rows_with_any_price_like+=1
            for c in cands:
                p=c["path"]
                path_counts[p]+=1
                path_symbol_counts[p].add(symbol)
                sym_paths.add(p)
                if len(path_value_examples[p])<5:
                    path_value_examples[p].append({"symbol":symbol,"as_of":d,"value":c["value"]})
            if n>=args.max_replay_rows_per_symbol: break
        if n:
            symbols_examined+=1
            per_symbol_price_path_sets[symbol]=sorted(sym_paths)

    price_path_registry=[
        {
            "path":p,
            "observation_count":path_counts[p],
            "symbol_count":len(path_symbol_counts[p]),
            "examples":path_value_examples[p],
        }
        for p in sorted(path_counts,key=lambda x:(-path_counts[x],x))
    ]

    # Frozen daily materialization inventory. Do not assume filename convention.
    all_files=sorted(p for p in dr.rglob("*") if p.is_file())
    ext_counts=Counter("".join(p.suffixes) or "<none>" for p in all_files)
    depth_counts=Counter(len(p.relative_to(dr).parts) for p in all_files)
    name_samples=[str(p.relative_to(dr)) for p in all_files[:100]]

    inspected=[]
    for p in all_files[:args.max_daily_files_to_inspect]:
        x=inspect_file(p)
        x["relative_path"]=str(p.relative_to(dr))
        inspected.append(x)

    parse_counts=Counter(x["parse_mode"] for x in inspected)
    files_with_date_keys=sum(bool(x["date_key_candidates"]) for x in inspected)
    files_with_close_keys=sum(bool(x["close_key_candidates"]) for x in inspected)
    parse_errors=sum(x["error"] is not None for x in inspected)

    # Filename-resolution diagnostics against symbols.
    symbols=[p.name[:-9] for p in replay_files]
    direct_name_matches=0
    basename_contains_matches=0
    examples_by_symbol={}
    lower_files=[(p,p.name.lower(),str(p.relative_to(dr)).lower()) for p in all_files]
    for symbol in symbols:
        s=symbol.lower()
        exact=[p for p,n,r in lower_files if n in (f"{s}.json",f"{s}.json.gz",f"{s}.jsonl",f"{s}.jsonl.gz",f"{s}.csv",f"{s}.csv.gz")]
        contains=[p for p,n,r in lower_files if s in n]
        if exact: direct_name_matches+=1
        if contains: basename_contains_matches+=1
        if len(examples_by_symbol)<25 and contains:
            examples_by_symbol[symbol]=[str(p.relative_to(dr)) for p in contains[:10]]

    # Candidate reference-price authority: only recommend paths with broad symbol coverage.
    broad_paths=[
        x for x in price_path_registry
        if x["symbol_count"] >= max(1,int(symbols_examined*0.90))
    ]
    reference_price_candidate_status=(
        "BROAD_CANDIDATE_PATHS_FOUND_REQUIRES_EXACT_VALUE_CONSISTENCY_REPLAY"
        if broad_paths else
        "NO_BROAD_REFERENCE_PRICE_PATH_FOUND_REQUIRES_SOURCE_CONTRACT_REPAIR"
    )

    daily_resolution_status=(
        "DAILY_ARTIFACT_SCHEMA_DISCOVERABLE"
        if files_with_date_keys and files_with_close_keys and parse_errors < len(inspected)
        else "DAILY_ARTIFACT_SCHEMA_NOT_YET_DISCOVERABLE"
    )

    report={
        "version":VERSION,
        "status":"READY",
        "backfill_authority_sha256":sha256_file(bp),
        "scope":{
            "development_only":True,
            "feature_matrix_mutated":False,
            "feature_semantics_changed":False,
            "outcome_or_target_file_opened":False,
            "validation_data_opened":False,
            "final_holdout_data_opened":False,
            "model_training_performed":False,
            "production_authority_effect":False,
        },
        "upstream_zero_coverage_features":list(expected_zero),
        "reference_price_forensics":{
            "symbols_examined":symbols_examined,
            "rows_examined":rows_examined,
            "rows_with_any_price_like_candidate":rows_with_any_price_like,
            "distinct_price_like_path_count":len(price_path_registry),
            "path_registry":price_path_registry,
            "broad_candidate_paths":broad_paths,
            "status":reference_price_candidate_status,
        },
        "daily_materialization_forensics":{
            "root":str(dr),
            "total_file_count":len(all_files),
            "extension_distribution":dict(ext_counts),
            "path_depth_distribution":dict(depth_counts),
            "name_samples":name_samples,
            "inspected_file_count":len(inspected),
            "parse_mode_distribution":dict(parse_counts),
            "files_with_date_key_candidates":files_with_date_keys,
            "files_with_close_key_candidates":files_with_close_keys,
            "parse_error_count":parse_errors,
            "exact_symbol_basename_match_count":direct_name_matches,
            "symbol_basename_contains_match_count":basename_contains_matches,
            "symbol_path_examples":examples_by_symbol,
            "status":daily_resolution_status,
        },
        "forensic_conclusion":"ZERO_COVERAGE_IS_SOURCE_RESOLUTION_NOT_FEATURE_EVIDENCE",
        "F020_native_atr_proves_replay_payload_extractability":True,
        "automatic_backfill_semantic_change_authorized":False,
        "next_step":"BUILD_M77_19_8_4_2_REFERENCE_PRICE_AND_FROZEN_DAILY_SOURCE_RESOLVER_AUTHORITY",
    }

    oj=resolve(root,args.output_json); oc=resolve(root,args.output_csv)
    atomic_json(oj,report)

    oc.parent.mkdir(parents=True,exist_ok=True)
    fields=["relative_path","parse_mode","top_level_type","size_bytes","date_keys","close_keys","error"]
    with oc.open("w",encoding="utf-8",newline="") as fh:
        import csv
        w=csv.DictWriter(fh,fieldnames=fields); w.writeheader()
        for x in inspected:
            w.writerow({
                "relative_path":x["relative_path"],
                "parse_mode":x["parse_mode"],
                "top_level_type":x["top_level_type"],
                "size_bytes":x["size_bytes"],
                "date_keys":"|".join(sorted(x["date_key_candidates"])),
                "close_keys":"|".join(sorted(x["close_key_candidates"])),
                "error":x["error"] or "",
            })

    print("=== M77.19.8.4.1 BACKFILL SOURCE-RESOLUTION & REFERENCE-PRICE FORENSICS ===")
    print("status: READY")
    print("upstream_zero_coverage_features:",list(expected_zero))
    print("reference_price_symbols_examined:",symbols_examined)
    print("reference_price_rows_examined:",rows_examined)
    print("rows_with_any_price_like_candidate:",rows_with_any_price_like)
    print("distinct_price_like_path_count:",len(price_path_registry))
    print("top_price_like_paths:",[(x["path"],x["observation_count"],x["symbol_count"]) for x in price_path_registry[:15]])
    print("reference_price_status:",reference_price_candidate_status)
    print("daily_materialization_total_file_count:",len(all_files))
    print("daily_extension_distribution:",dict(ext_counts))
    print("daily_parse_mode_distribution:",dict(parse_counts))
    print("daily_files_with_date_keys:",files_with_date_keys)
    print("daily_files_with_close_keys:",files_with_close_keys)
    print("exact_symbol_basename_match_count:",direct_name_matches)
    print("symbol_basename_contains_match_count:",basename_contains_matches)
    print("daily_resolution_status:",daily_resolution_status)
    print("forensic_conclusion: ZERO_COVERAGE_IS_SOURCE_RESOLUTION_NOT_FEATURE_EVIDENCE")
    print("feature_matrix_mutated: False")
    print("outcome_or_target_file_opened: False")
    print("validation_data_opened: False")
    print("final_holdout_data_opened: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_4_2_REFERENCE_PRICE_AND_FROZEN_DAILY_SOURCE_RESOLVER_AUTHORITY")
    print("report:",oj)
    print("csv:",oc)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
