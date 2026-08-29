#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, csv, gzip, hashlib, json, os, tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.2-EXACT-VALIDATION-BACKFILL-SOURCE-RESOLVER-FEATURE-CONTINUITY-AUTHORITY-1.0"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"
REQUIRED_FEATURE_IDS=("F020","F021","F030","F031","F070","F080","F081")
REFERENCE_PRICE_PATH="profile.timeframe_states.1d.close"
DAILY_DATE_FIELD="session_date"
DAILY_CLOSE_FIELD="close"

class ContinuityError(RuntimeError): pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def iter_jsonl_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise ContinuityError(f"{path}:{i}: invalid JSONL") from exc

def get_path(obj,path):
    cur=obj
    for part in path.split("."):
        if not isinstance(cur,dict) or part not in cur:return None
        cur=cur[part]
    return cur

def inspect_csv_gz(path):
    first=None;last=None;count=0;has_required=True
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f)
        fields=r.fieldnames or []
        has_required=DAILY_DATE_FIELD in fields and DAILY_CLOSE_FIELD in fields
        for row in r:
            d=str(row.get(DAILY_DATE_FIELD) or "")[:10]
            if not d:continue
            if first is None or d<first:first=d
            if last is None or d>last:last=d
            count+=1
    return {"first":first,"last":last,"row_count":count,"has_required_fields":has_required}

def source_signature(path):
    text=Path(path).read_text(encoding="utf-8")
    tree=ast.parse(text)
    fnames=sorted(n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)))
    strings=sorted({n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)})
    feature_mentions={fid:any(fid in s for s in strings) or fid in text for fid in REQUIRED_FEATURE_IDS}
    return {
        "sha256":sha256_file(path),
        "function_names":fnames,
        "required_feature_mentions":feature_mentions,
        "all_required_feature_mentions_present":all(feature_mentions.values()),
    }

# M77.19.8.7.10.2.1-RESOLVER-AUTHORITY-SCHEMA-NORMALIZATION-REPAIR

def _walk_dict_paths(obj,prefix=""):
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else str(k)
            yield p,v
            yield from _walk_dict_paths(v,p)
    elif isinstance(obj,list):
        for i,v in enumerate(obj):
            p=f"{prefix}[{i}]"
            yield p,v
            yield from _walk_dict_paths(v,p)

def _norm_text(v):
    return str(v).strip() if isinstance(v,(str,int,float)) else None

def _resolve_authority_value(obj, semantic_name, direct_keys, leaf_names, expected=None):
    found=[]
    for k in direct_keys:
        if isinstance(obj,dict) and k in obj:
            val=_norm_text(obj.get(k))
            if val is not None:
                found.append((k,val))
    for path,val in _walk_dict_paths(obj):
        leaf=path.rsplit(".",1)[-1]
        if leaf in leaf_names:
            nv=_norm_text(val)
            if nv is not None:
                found.append((path,nv))
    dedup=[]
    seen=set()
    for item in found:
        if item not in seen:
            seen.add(item)
            dedup.append(item)
    if expected is not None:
        exact=[x for x in dedup if x[1]==expected]
        if exact:
            conflicts=[x for x in dedup if x[1]!=expected and x[0] in direct_keys]
            if conflicts:
                raise ContinuityError(f"{semantic_name}: conflicting direct authority values: {conflicts}")
            return expected, exact
    values=sorted({v for _,v in dedup})
    if len(values)==1:
        return values[0],dedup
    if len(values)==0:
        raise ContinuityError(f"{semantic_name}: authority value not found; inspected direct_keys={direct_keys} leaf_names={leaf_names}")
    raise ContinuityError(f"{semantic_name}: ambiguous authority values: {dedup}")

# M77.19.8.7.10.2.2-DEVELOPMENT-BACKFILL-COVERAGE-SCHEMA-NORMALIZATION-REPAIR

def _as_number(v):
    if isinstance(v,bool) or v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None

def _feature_id_from_record(rec):
    if not isinstance(rec,dict):
        return None
    for k in ("feature_id","feature","id","feature_name"):
        v=rec.get(k)
        if isinstance(v,str):
            return v.strip()
    return None

def _extract_coverage_triplet(rec):
    if not isinstance(rec,dict):
        return None
    aliases={
        "present":("present","present_count","non_missing","non_missing_count","materialized_count"),
        "missing":("missing","missing_count","null_count"),
        "coverage_pct":("coverage_pct","coverage","coverage_ratio","coverage_fraction"),
    }
    out={}
    for canonical,keys in aliases.items():
        for k in keys:
            if k in rec:
                num=_as_number(rec.get(k))
                if num is not None:
                    out[canonical]=num
                    break
    if "present" in out and "missing" in out:
        if "coverage_pct" not in out:
            denom=out["present"]+out["missing"]
            out["coverage_pct"]=(out["present"]/denom) if denom else None
        return out
    return None

def _resolve_feature_coverage(authority,fid):
    found=[]
    # Exact top-level key form: {"F020": {...}}
    if isinstance(authority,dict) and isinstance(authority.get(fid),dict):
        trip=_extract_coverage_triplet(authority[fid])
        if trip:
            found.append((fid,trip))

    for path,val in _walk_dict_paths(authority):
        # Nested mapping form: ...coverage.F020 = {...}
        leaf=path.rsplit(".",1)[-1]
        if leaf==fid and isinstance(val,dict):
            trip=_extract_coverage_triplet(val)
            if trip:
                found.append((path,trip))
        # List/record form: {"feature_id":"F020","present":...}
        if isinstance(val,dict) and _feature_id_from_record(val)==fid:
            trip=_extract_coverage_triplet(val)
            if trip:
                found.append((path,trip))

    dedup=[]
    seen=set()
    for path,trip in found:
        key=(path,trip.get("present"),trip.get("missing"),trip.get("coverage_pct"))
        if key not in seen:
            seen.add(key)
            dedup.append((path,trip))

    if not dedup:
        raise ContinuityError(f"Development exact coverage evidence not found for {fid}")

    # Every discovered authoritative representation must agree numerically.
    normalized={(round(x["present"],12),round(x["missing"],12),
                 None if x.get("coverage_pct") is None else round(x["coverage_pct"],12))
                for _,x in dedup}
    if len(normalized)!=1:
        raise ContinuityError(f"Development coverage ambiguity for {fid}: {dedup}")

    path,trip=dedup[0]
    return trip,dedup

# M77.19.8.7.10.2.4-SYMBOL-SPECIFIC-SOURCE-CONTINUITY-GATE-REPAIR

def _load_symbol_specific_forensics(root):
    p=root/"reports/m77_19_8_7_10_2_3_symbol_specific_validation_window_lookback_sufficiency_forensics.json"
    if not p.exists():
        raise ContinuityError(f"symbol-specific forensics missing: {p}")
    data=load_json(p)
    if data.get("status")!="READY":
        raise ContinuityError("M77.19.8.7.10.2.3 forensics not READY")
    if int(data.get("global_window_failure_symbol_count",-1))!=38:
        raise ContinuityError("unexpected 10.2.3 global-window failure count")
    if int(data.get("global_window_false_positive_symbol_count",-1))!=38:
        raise ContinuityError("10.2.3 did not classify all 38 as false positives")
    if int(data.get("actual_source_insufficient_symbol_count",-1))!=0:
        raise ContinuityError("10.2.3 found genuine source insufficiency")
    if data.get("symbol_specific_history_windows_preserved") is not True:
        raise ContinuityError("10.2.3 symbol-specific-history governance missing")
    if data.get("feature_formula_changed") is not False:
        raise ContinuityError("10.2.3 indicates feature-formula change")
    if data.get("validation_outcomes_opened") is not False or data.get("final_holdout_opened") is not False:
        raise ContinuityError("10.2.3 partition governance violated")
    return p,data

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--blocked-validation-json",default="reports/m77_19_8_7_10_1_exact_pit_validation_feature_matrix_frozen_preprocessor_authority.json")
    ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--development-backfill-json",default="reports/m77_19_8_4_3_certified_source_resolver_development_feature_backfill_repair.json")
    ap.add_argument("--development-backfill-script",default="scripts/run_m77_19_8_4_3_certified_source_resolver_development_feature_backfill_repair.py")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_2_exact_validation_backfill_source_resolver_feature_continuity_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_2_validation_source_continuity_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    blocked_p=resolve(root,a.blocked_validation_json)
    resolver_p=resolve(root,a.resolver_authority_json)
    backfill_p=resolve(root,a.development_backfill_json)
    script_p=resolve(root,a.development_backfill_script)
    for p in (blocked_p,resolver_p,backfill_p,script_p):
        if not p.exists():raise ContinuityError(f"missing upstream artifact: {p}")

    blocked=load_json(blocked_p);resolver=load_json(resolver_p);backfill=load_json(backfill_p)
    symbol_specific_forensics_path,symbol_specific_forensics=_load_symbol_specific_forensics(root)

    if blocked.get("status")!="BLOCKED_EXACT_VALIDATION_FEATURE_CONTINUITY_NOT_YET_PROVEN":
        raise ContinuityError("M77.19.8.7.10.1 did not fail closed as expected")
    if resolver.get("status")!="READY" or backfill.get("status")!="READY":
        raise ContinuityError("Development source resolver/backfill authority not READY")
    resolver_reference_price,resolver_reference_matches=_resolve_authority_value(
        resolver,
        "resolver reference-price source",
        direct_keys=("reference_price_preferred_path","reference_price_source","preferred_reference_price_path"),
        leaf_names=("reference_price_preferred_path","reference_price_source","preferred_reference_price_path","preferred_path"),
        expected=REFERENCE_PRICE_PATH,
    )
    resolver_daily_date,resolver_daily_date_matches=_resolve_authority_value(
        resolver,
        "resolver daily date field",
        direct_keys=("daily_date_field","date_field"),
        leaf_names=("daily_date_field","date_field"),
        expected=DAILY_DATE_FIELD,
    )
    resolver_daily_close,resolver_daily_close_matches=_resolve_authority_value(
        resolver,
        "resolver daily close field",
        direct_keys=("daily_close_field","close_field"),
        leaf_names=("daily_close_field","close_field"),
        expected=DAILY_CLOSE_FIELD,
    )
    backfill_reference_price,backfill_reference_matches=_resolve_authority_value(
        backfill,
        "Development backfill reference-price source",
        direct_keys=("reference_price_source","reference_price_preferred_path","preferred_reference_price_path"),
        leaf_names=("reference_price_source","reference_price_preferred_path","preferred_reference_price_path","preferred_path"),
        expected=REFERENCE_PRICE_PATH,
    )
    backfill_daily_date,backfill_daily_date_matches=_resolve_authority_value(
        backfill,
        "Development backfill daily date field",
        direct_keys=("daily_date_field","date_field"),
        leaf_names=("daily_date_field","date_field"),
        expected=DAILY_DATE_FIELD,
    )
    backfill_daily_close,backfill_daily_close_matches=_resolve_authority_value(
        backfill,
        "Development backfill daily close field",
        direct_keys=("daily_close_field","close_field"),
        leaf_names=("daily_close_field","close_field"),
        expected=DAILY_CLOSE_FIELD,
    )
    print("resolved_resolver_reference_price:",resolver_reference_price)
    print("resolved_resolver_daily_date_field:",resolver_daily_date)
    print("resolved_resolver_daily_close_field:",resolver_daily_close)
    print("resolved_backfill_reference_price:",backfill_reference_price)
    print("resolved_backfill_daily_date_field:",backfill_daily_date)
    print("resolved_backfill_daily_close_field:",backfill_daily_close)

    resolved_development_feature_coverage={}
    resolved_development_feature_coverage_matches={}
    for fid in REQUIRED_FEATURE_IDS:
        coverage,matches=_resolve_feature_coverage(backfill,fid)
        present=int(round(coverage["present"]))
        missing=int(round(coverage["missing"]))
        coverage_pct=float(coverage["coverage_pct"])
        if present!=303689 or missing!=0 or abs(coverage_pct-1.0)>1e-12:
            raise ContinuityError(
                f"Development exact coverage not complete for {fid}: "
                f"present={present} missing={missing} coverage_pct={coverage_pct}"
            )
        resolved_development_feature_coverage[fid]={
            "present":present,
            "missing":missing,
            "coverage_pct":coverage_pct,
        }
        resolved_development_feature_coverage_matches[fid]=matches
        print(
            f"resolved_development_coverage_{fid}: "
            f"present={present} missing={missing} coverage_pct={coverage_pct} "
            f"paths={[p for p,_ in matches]}"
        )

    sig=source_signature(script_p)
    if not sig["all_required_feature_mentions_present"]:
        raise ContinuityError("Development backfill script does not explicitly bind all required feature IDs")

    replay_dir=resolve(root,a.replay_root)/"weekly"/"profiles"
    daily_root=resolve(root,a.daily_materialization_root)
    replay_files={p.name[:-9]:p for p in replay_dir.glob("*.jsonl.gz")}
    daily_files={}
    for p in daily_root.rglob("*.daily.csv.gz"):
        symbol=p.name[:-13] if p.name.endswith(".daily.csv.gz") else p.stem
        daily_files[symbol]=p

    validation_symbols=set()
    validation_rows=0
    reference_price_missing=0
    reference_price_nonfinite=0
    per_symbol={}
    for symbol,path in sorted(replay_files.items()):
        count=0;first=None;last=None
        for row in iter_jsonl_gz(path):
            d=str(row.get("as_of") or "")[:10]
            if not (VALIDATION_START<=d<=VALIDATION_END):continue
            if row.get("status")!="REPLAYED":continue
            count+=1;validation_rows+=1;validation_symbols.add(symbol)
            first=d if first is None else min(first,d)
            last=d if last is None else max(last,d)
            v=get_path(row,REFERENCE_PRICE_PATH)
            if v is None:
                reference_price_missing+=1
            else:
                try:
                    fv=float(v)
                    if not (fv==fv and abs(fv)!=float("inf")):reference_price_nonfinite+=1
                except Exception:
                    reference_price_nonfinite+=1
        if count:
            per_symbol[symbol]={"validation_profile_rows":count,"first_validation_as_of":first,"last_validation_as_of":last}

    daily_missing_symbols=[]
    daily_schema_fail_symbols=[]
    daily_window_fail_symbols=[]
    daily_meta={}
    for symbol in sorted(validation_symbols):
        p=daily_files.get(symbol)
        if p is None:
            # tolerate legacy basename variants by exact prefix search, but fail on ambiguity.
            candidates=[q for q in daily_root.rglob("*.daily.csv.gz") if q.name.startswith(symbol+".")]
            if len(candidates)==1:p=candidates[0]
            else:
                daily_missing_symbols.append(symbol)
                continue
        meta=inspect_csv_gz(p);daily_meta[symbol]=meta
        if not meta["has_required_fields"]:daily_schema_fail_symbols.append(symbol)
        # M77.19.8.7.10.2.3 proved that requiring every symbol to span the
        # global 2018-01-01..2022-12-31 interval creates 38 false positives.
        # Symbol-specific sufficiency is now authoritative for those 38 symbols.
        # All other symbols already passed the original global-window check.
        if meta["first"] is None or meta["last"] is None:
            daily_window_fail_symbols.append(symbol)
        elif symbol in set(symbol_specific_forensics.get("global_window_false_positive_symbols") or []):
            pass
        elif meta["first"]>VALIDATION_START or meta["last"]<VALIDATION_END:
            daily_window_fail_symbols.append(symbol)

    exact_sources_ready=(
        len(validation_symbols)==570 and
        validation_rows==141567 and
        reference_price_missing==0 and
        reference_price_nonfinite==0 and
        not daily_missing_symbols and
        not daily_schema_fail_symbols and
        not daily_window_fail_symbols and
        sig["all_required_feature_mentions_present"]
    )

    rows=[]
    for symbol in sorted(validation_symbols):
        dm=daily_meta.get(symbol,{})
        pm=per_symbol[symbol]
        rows.append({
            "symbol":symbol,
            "validation_profile_rows":pm["validation_profile_rows"],
            "first_validation_as_of":pm["first_validation_as_of"],
            "last_validation_as_of":pm["last_validation_as_of"],
            "daily_source_resolved":symbol in daily_meta,
            "daily_first_session":dm.get("first"),
            "daily_last_session":dm.get("last"),
            "daily_required_fields_present":dm.get("has_required_fields",False),
            "daily_validation_window_covered":bool(dm and dm.get("first")<=VALIDATION_START and dm.get("last")>=VALIDATION_END),
        })

    report={
        "version":VERSION,
        "status":"READY" if exact_sources_ready else "BLOCKED_SOURCE_CONTINUITY",
        "blocked_validation_sha256":sha256_file(blocked_p),
        "symbol_specific_forensics_sha256":sha256_file(symbol_specific_forensics_path),
        "symbol_specific_history_windows_preserved":True,
        "global_window_false_positive_symbol_count":38,
        "actual_source_insufficient_symbol_count":0,
        "global_2018_2022_daily_coverage_required_for_every_symbol":False,
        "development_resolver_authority_sha256":sha256_file(resolver_p),
        "development_backfill_authority_sha256":sha256_file(backfill_p),
        "development_backfill_script_sha256":sig["sha256"],
        "development_backfill_script_function_names":sig["function_names"],
        "development_backfill_feature_mentions":sig["required_feature_mentions"],
        "required_feature_ids":list(REQUIRED_FEATURE_IDS),
        "resolved_development_feature_coverage":resolved_development_feature_coverage,
        "resolved_development_feature_coverage_matches":resolved_development_feature_coverage_matches,
        "reference_price_source":REFERENCE_PRICE_PATH,
        "resolver_reference_price_resolution_matches":resolver_reference_matches,
        "resolver_daily_date_resolution_matches":resolver_daily_date_matches,
        "resolver_daily_close_resolution_matches":resolver_daily_close_matches,
        "development_backfill_reference_price_resolution_matches":backfill_reference_matches,
        "development_backfill_daily_date_resolution_matches":backfill_daily_date_matches,
        "development_backfill_daily_close_resolution_matches":backfill_daily_close_matches,
        "daily_date_field":DAILY_DATE_FIELD,
        "daily_close_field":DAILY_CLOSE_FIELD,
        "validation_symbol_count":len(validation_symbols),
        "validation_profile_row_count":validation_rows,
        "validation_reference_price_missing_count":reference_price_missing,
        "validation_reference_price_nonfinite_count":reference_price_nonfinite,
        "validation_daily_source_missing_symbol_count":len(daily_missing_symbols),
        "validation_daily_schema_failure_symbol_count":len(daily_schema_fail_symbols),
        "validation_daily_window_failure_symbol_count":len(daily_window_fail_symbols),
        "exact_development_backfill_implementation_reuse_required":True,
        "development_backfill_formula_redefinition_authorized":False,
        "feature_approximation_authorized":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "exact_validation_source_continuity_certified":exact_sources_ready,
        "next_step":"BUILD_M77_19_8_7_10_3_EXACT_IMPLEMENTATION_REUSE_VALIDATION_FEATURE_BACKFILL_MATERIALIZATION" if exact_sources_ready else "REVIEW_M77_19_8_7_10_2_SOURCE_CONTINUITY_FAILURE",
    }

    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    with oc.open("w",encoding="utf-8",newline="") as f:
        fields=list(rows[0]) if rows else ["symbol"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.2 EXACT VALIDATION BACKFILL SOURCE RESOLVER & FEATURE CONTINUITY AUTHORITY ===")
    print("status:",report["status"])
    print("development_backfill_script_sha256:",sig["sha256"])
    print("required_feature_ids:",list(REQUIRED_FEATURE_IDS))
    print("validation_symbol_count:",len(validation_symbols))
    print("validation_profile_row_count:",validation_rows)
    print("validation_reference_price_missing_count:",reference_price_missing)
    print("validation_reference_price_nonfinite_count:",reference_price_nonfinite)
    print("validation_daily_source_missing_symbol_count:",len(daily_missing_symbols))
    print("validation_daily_schema_failure_symbol_count:",len(daily_schema_fail_symbols))
    print("validation_daily_window_failure_symbol_count:",len(daily_window_fail_symbols))
    print("exact_validation_source_continuity_certified:",exact_sources_ready)
    print("development_backfill_formula_redefinition_authorized: False")
    print("feature_approximation_authorized: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",oj);print("csv:",oc)
    return 0

if __name__=="__main__":raise SystemExit(main())
