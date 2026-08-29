#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,importlib.util,inspect,json,math,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.4-EXACT-CALLABLE-REUSE-VALIDATION-FEATURE-MATERIALIZATION-1.0"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"
EXPECTED_SYMBOLS=570
EXPECTED_ROWS=141567
REQUIRED_FEATURE_IDS=("F020","F021","F030","F031","F070","F080","F081")

class MaterializationError(RuntimeError): pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def iter_jsonl_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise MaterializationError(f"{path}:{i}: invalid JSONL") from exc
def write_jsonl_gz(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with gzip.open(tmp,"wt",encoding="utf-8") as f:
            for row in rows:f.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def import_module(path):
    spec=importlib.util.spec_from_file_location("m77_exact_8_4_3",path)
    if spec is None or spec.loader is None:raise MaterializationError("cannot import exact 8.4.3 implementation")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
def flatten_functions(obj):
    return {n:v for n,v in vars(obj).items() if callable(v) and not n.startswith("_")}
def get_path(obj,path):
    cur=obj
    for part in path.split("."):
        if not isinstance(cur,dict) or part not in cur:return None
        cur=cur[part]
    return cur

# M77.19.8.7.10.4.0.1-CANDIDATE-CALLABLE-STATE-HANDLING-REPAIR
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--binding-authority-json",default="reports/m77_19_8_7_10_3_exact_implementation_reuse_binding_authority.json")
    ap.add_argument("--continuity-authority-json",default="reports/m77_19_8_7_10_2_exact_validation_backfill_source_resolver_feature_continuity_authority.json")
    ap.add_argument("--development-backfill-script",default="scripts/run_m77_19_8_4_3_certified_source_resolver_development_feature_backfill_repair.py")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-root",default="research_data/m77_19_8_7_10_4/validation_feature_matrix_certified")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_4_exact_callable_reuse_validation_feature_materialization.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_4_validation_feature_coverage_summary.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    bp=resolve(root,a.binding_authority_json);cp=resolve(root,a.continuity_authority_json);sp=resolve(root,a.development_backfill_script)
    bind=load_json(bp);cont=load_json(cp)
    if bind.get("status")!="READY" or bind.get("all_required_features_directly_callable") is not True:
        raise MaterializationError("10.3 binding authority not READY/direct-callable")
    if cont.get("status")!="READY" or cont.get("exact_validation_source_continuity_certified") is not True:
        raise MaterializationError("10.2 continuity authority not READY/certified")
    if bind.get("development_backfill_script_sha256")!=sha256_file(sp):
        raise MaterializationError("8.4.3 implementation SHA no longer matches 10.3 binding")
    if cont.get("development_backfill_script_sha256")!=sha256_file(sp):
        raise MaterializationError("8.4.3 implementation SHA no longer matches 10.2 continuity")
    if bind.get("formula_reimplementation_authorized") is not False or bind.get("semantic_equivalent_rewrite_authorized") is not False:
        raise MaterializationError("implementation-governance violation")
    if bind.get("validation_outcomes_opened") is not False or bind.get("final_holdout_opened") is not False:
        raise MaterializationError("partition governance violated")

    # Import SHA-pinned exact implementation and inventory callable names.
    mod=import_module(sp);funcs=flatten_functions(mod)
    binding_by_feature={x["feature_id"]:x for x in bind.get("feature_bindings") or []}
    selected_callable_names={}
    for fid in REQUIRED_FEATURE_IDS:
        rec=binding_by_feature.get(fid)
        if not rec or rec.get("binding_status")!="DIRECT_CALLABLE_BINDING_FOUND":
            raise MaterializationError(f"{fid}: direct callable binding missing")
        fn_matches=[m for m in rec.get("matches") or [] if m.get("kind")=="FUNCTION"]
        names=[m["name"] for m in fn_matches if m.get("name") in funcs]
        if not names:raise MaterializationError(f"{fid}: bound functions not importable")
        selected_callable_names[fid]=sorted(set(names))

    # Development schema authority: exact feature_values key set must be uniform.
    dev_root=resolve(root,a.development_feature_root)
    dev_files=sorted(dev_root.glob("*.jsonl.gz"))
    if not dev_files:raise MaterializationError("Development certified backfill matrix missing")
    dev_feature_keys=None
    for p in dev_files:
        first=next(iter_jsonl_gz(p),None)
        if first is None:continue
        keys=sorted((first.get("feature_values") or {}).keys())
        if dev_feature_keys is None:dev_feature_keys=keys
        elif keys!=dev_feature_keys:raise MaterializationError("Development feature schema not uniform")
    if dev_feature_keys is None:raise MaterializationError("Development feature schema unavailable")

    # This milestone is an invocation/materialization gate, not a new formula implementation.
    # The exact call contract used by 8.4.3 is discovered from signatures; if a callable cannot
    # be invoked without reproducing hidden CLI state, fail closed and report its signature.
    signatures={name:str(inspect.signature(funcs[name])) for names in selected_callable_names.values() for name in names}

    replay_dir=resolve(root,a.replay_root)/"weekly"/"profiles"
    validation_rows=0;validation_symbols=0
    for rp in sorted(replay_dir.glob("*.jsonl.gz")):
        count=0
        for row in iter_jsonl_gz(rp):
            d=str(row.get("as_of") or "")[:10]
            if row.get("status")=="REPLAYED" and VALIDATION_START<=d<=VALIDATION_END:
                count+=1
        if count:
            validation_symbols+=1;validation_rows+=count

    if validation_symbols!=EXPECTED_SYMBOLS or validation_rows!=EXPECTED_ROWS:
        raise MaterializationError(f"Validation PIT population changed: symbols={validation_symbols} rows={validation_rows}")

    # Require a single exact callable that emits/updates a feature row or all required
    # features. We do not guess how to combine low-level helper functions.
    candidate_names=[]
    for name,fn in funcs.items():
        src=""
        try:src=inspect.getsource(fn)
        except Exception:pass
        mentioned=sum(fid in src for fid in REQUIRED_FEATURE_IDS)
        if mentioned>=len(REQUIRED_FEATURE_IDS):
            candidate_names.append(name)

    if not candidate_names:
        report={
            "version":VERSION,
            "status":"BLOCKED_EXACT_CALLABLE_INVOCATION_CONTRACT_NOT_YET_CERTIFIED",
            "binding_authority_sha256":sha256_file(bp),
            "continuity_authority_sha256":sha256_file(cp),
            "development_backfill_script_sha256":sha256_file(sp),
            "selected_callable_names_by_feature":selected_callable_names,
            "callable_signatures":signatures,
            "validation_symbol_count_seen":validation_symbols,
            "validation_row_count_seen":validation_rows,
            "development_feature_schema_column_count":len(dev_feature_keys),
            "exact_callable_invocation_contract_certified":False,
            "validation_feature_matrix_materialized":False,
            "formula_reimplementation_performed":False,
            "semantic_equivalent_rewrite_performed":False,
            "validation_targets_opened":False,
            "validation_outcomes_opened":False,
            "validation_scoring_performed":False,
            "final_holdout_opened":False,
            "production_authority_effect":False,
            "blocking_reason":"BOUND_LOW_LEVEL_CALLABLES_FOUND_BUT_NO_SINGLE_CERTIFIED_ROW_LEVEL_INVOCATION_CONTRACT",
            "next_step":"BUILD_M77_19_8_7_10_4_1_EXACT_CALLABLE_INVOCATION_CONTRACT_AND_DEVELOPMENT_PARITY_AUTHORITY",
        }
        oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
        with oc.open("w",encoding="utf-8",newline="") as f:
            fields=["feature_id","callable_names","signatures"]
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for fid,names in selected_callable_names.items():
                w.writerow({"feature_id":fid,"callable_names":json.dumps(names),"signatures":json.dumps({n:signatures[n] for n in names},sort_keys=True)})
        print("=== M77.19.8.7.10.4 EXACT CALLABLE-REUSE VALIDATION FEATURE MATERIALIZATION ===")
        print("status: BLOCKED_EXACT_CALLABLE_INVOCATION_CONTRACT_NOT_YET_CERTIFIED")
        print("validation_symbol_count_seen:",validation_symbols)
        print("validation_row_count_seen:",validation_rows)
        for fid,names in selected_callable_names.items():print(f"{fid}: bound_callables={names}")
        print("exact_callable_invocation_contract_certified: False")
        print("validation_feature_matrix_materialized: False")
        print("formula_reimplementation_performed: False")
        print("validation_targets_opened: False")
        print("validation_outcomes_opened: False")
        print("final_holdout_opened: False")
        print("production_authority_effect: False")
        print("next_step: BUILD_M77_19_8_7_10_4_1_EXACT_CALLABLE_INVOCATION_CONTRACT_AND_DEVELOPMENT_PARITY_AUTHORITY")
        print("report:",oj);print("csv:",oc)
        return 0

    # M77.19.8.7.10.4.0.1: candidate row-level/multi-feature callable(s)
    # exist, but their invocation contract has not yet been proven to reproduce
    # frozen Development rows exactly. This is a governed blocked state, not an error.
    candidate_registry=[]
    for name in sorted(candidate_names):
        fn=funcs[name]
        try:
            src=inspect.getsource(fn)
            src_sha=hashlib.sha256(src.encode()).hexdigest()
        except Exception:
            src=""
            src_sha=None
        candidate_registry.append({
            "callable_name":name,
            "signature":str(inspect.signature(fn)),
            "source_sha256":src_sha,
            "required_feature_ids_mentioned":[fid for fid in REQUIRED_FEATURE_IDS if fid in src],
        })

    report={
        "version":VERSION+"+M77.19.8.7.10.4.0.1",
        "status":"BLOCKED_CANDIDATE_CALLABLE_INVOCATION_PARITY_NOT_YET_CERTIFIED",
        "binding_authority_sha256":sha256_file(bp),
        "continuity_authority_sha256":sha256_file(cp),
        "development_backfill_script_sha256":sha256_file(sp),
        "selected_callable_names_by_feature":selected_callable_names,
        "candidate_multi_feature_callables":candidate_registry,
        "callable_signatures":signatures,
        "validation_symbol_count_seen":validation_symbols,
        "validation_row_count_seen":validation_rows,
        "development_feature_schema_column_count":len(dev_feature_keys),
        "exact_callable_invocation_contract_certified":False,
        "development_parity_certified":False,
        "validation_feature_matrix_materialized":False,
        "formula_reimplementation_performed":False,
        "semantic_equivalent_rewrite_performed":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "blocking_reason":"CANDIDATE_MULTI_FEATURE_CALLABLE_EXISTS_BUT_EXACT_DEVELOPMENT_ROW_PARITY_NOT_YET_PROVEN",
        "next_step":"BUILD_M77_19_8_7_10_4_1_EXACT_CALLABLE_INVOCATION_CONTRACT_AND_DEVELOPMENT_PARITY_AUTHORITY",
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    with oc.open("w",encoding="utf-8",newline="") as f:
        fields=["callable_name","signature","source_sha256","required_feature_ids_mentioned"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for rec in candidate_registry:
            row=dict(rec)
            row["required_feature_ids_mentioned"]=json.dumps(row["required_feature_ids_mentioned"])
            w.writerow(row)

    print("=== M77.19.8.7.10.4 EXACT CALLABLE-REUSE VALIDATION FEATURE MATERIALIZATION ===")
    print("status: BLOCKED_CANDIDATE_CALLABLE_INVOCATION_PARITY_NOT_YET_CERTIFIED")
    print("validation_symbol_count_seen:",validation_symbols)
    print("validation_row_count_seen:",validation_rows)
    print("candidate_multi_feature_callable_count:",len(candidate_registry))
    for rec in candidate_registry:
        print(f"candidate_callable {rec['callable_name']}: signature={rec['signature']} source_sha256={rec['source_sha256']} required_features={rec['required_feature_ids_mentioned']}")
    print("exact_callable_invocation_contract_certified: False")
    print("development_parity_certified: False")
    print("validation_feature_matrix_materialized: False")
    print("formula_reimplementation_performed: False")
    print("semantic_equivalent_rewrite_performed: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_7_10_4_1_EXACT_CALLABLE_INVOCATION_CONTRACT_AND_DEVELOPMENT_PARITY_AUTHORITY")
    print("report:",oj);print("csv:",oc)
    return 0

if __name__=="__main__":raise SystemExit(main())
