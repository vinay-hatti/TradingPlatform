#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.5-EXACT-MAIN-REUSE-VALIDATION-FEATURE-MATRIX-MATERIALIZATION-1.0"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"
EXPECTED_SYMBOLS=570
EXPECTED_ROWS=141567
REQUIRED_FEATURE_IDS=("F020","F021","F030","F031","F070","F080","F081")

class ValidationMaterializationError(RuntimeError):pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
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
            except Exception as exc:raise ValidationMaterializationError(f"{path}:{i}: invalid JSONL") from exc
def write_jsonl_gz(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with gzip.open(tmp,"wt",encoding="utf-8") as f:
            for r in rows:f.write(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--parity-authority-json",default="reports/m77_19_8_7_10_4_2_exact_main_development_replay_parity_harness.json")
    ap.add_argument("--continuity-authority-json",default="reports/m77_19_8_7_10_2_exact_validation_backfill_source_resolver_feature_continuity_authority.json")
    ap.add_argument("--validation-authority-json",default="reports/m77_19_8_7_10_authorized_model_family_validation_only_evaluation_authority.json")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-root",default="research_data/m77_19_8_7_10_5/validation_feature_matrix_certified")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_5_exact_main_reuse_validation_feature_matrix_materialization.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_5_validation_feature_coverage_summary.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    pp=resolve(root,a.parity_authority_json);cp=resolve(root,a.continuity_authority_json);vp=resolve(root,a.validation_authority_json)
    parity=load_json(pp);continuity=load_json(cp);validation=load_json(vp)

    if parity.get("status")!="READY" or parity.get("development_parity_certified") is not True:
        raise ValidationMaterializationError("10.4.2 parity authority not READY/certified")
    if continuity.get("status")!="READY" or continuity.get("exact_validation_source_continuity_certified") is not True:
        raise ValidationMaterializationError("10.2 continuity authority not READY/certified")
    if validation.get("status")!="READY":
        raise ValidationMaterializationError("10 authorized Validation authority not READY")
    if validation.get("validation_feature_materialization_authorized") is not True:
        raise ValidationMaterializationError("Validation feature materialization not authorized")
    if validation.get("validation_feature_approximation_authorized") is not False:
        raise ValidationMaterializationError("Validation approximation governance violated")
    if validation.get("final_holdout_context_open_authorized") is not False or validation.get("final_holdout_outcomes_open_authorized") is not False:
        raise ValidationMaterializationError("Final Holdout governance violated")

    # Development schema authority
    dev_root=resolve(root,a.development_feature_root)
    dev_files=sorted(dev_root.glob("*.jsonl.gz"))
    if not dev_files:raise ValidationMaterializationError("Development feature matrix missing")
    dev_schema=None
    for p in dev_files:
        first=next(iter_jsonl_gz(p),None)
        if first is None:continue
        keys=sorted((first.get("feature_values") or {}).keys())
        if dev_schema is None:dev_schema=keys
        elif keys!=dev_schema:raise ValidationMaterializationError("Development schema not uniform")
    if dev_schema is None:raise ValidationMaterializationError("Development schema unavailable")

    # Exact certified replay contract cannot be run directly for Validation because
    # 8.4.3 is Development-partition hard-coded. This milestone therefore materializes
    # only the already-direct PIT feature columns from replay and records a fail-closed
    # requirement for the seven backfilled columns to be supplied by the exact 8.4.3
    # logic through a partition-parameterization adapter.
    replay_dir=resolve(root,a.replay_root)/"weekly"/"profiles"
    out_root=resolve(root,a.output_root)
    out_root.mkdir(parents=True,exist_ok=True)

    symbol_count=0;row_count=0
    backfill_missing={fid:0 for fid in REQUIRED_FEATURE_IDS}
    schema_mismatch=0

    for rp in sorted(replay_dir.glob("*.jsonl.gz")):
        symbol=rp.name[:-9]
        rows=[]
        for r in iter_jsonl_gz(rp):
            d=str(r.get("as_of") or "")[:10]
            if r.get("status")!="REPLAYED" or not (VALIDATION_START<=d<=VALIDATION_END):continue
            fv=r.get("feature_values")
            # PIT replay rows do not carry the 8.4.3 backfilled training feature_values;
            # we preserve this as an explicit blocked state rather than synthesizing.
            if not isinstance(fv,dict):
                fv={}
            for fid in REQUIRED_FEATURE_IDS:
                if fid not in fv or fv.get(fid) is None:
                    backfill_missing[fid]+=1
            rows.append({"symbol":symbol,"as_of":d,"feature_values":fv,"status":"VALIDATION_PIT_ROW_SEEN_BACKFILL_PENDING_EXACT_ADAPTER"})
        if rows:
            write_jsonl_gz(out_root/f"{symbol}.jsonl.gz",rows)
            symbol_count+=1;row_count+=len(rows)

    if symbol_count!=EXPECTED_SYMBOLS or row_count!=EXPECTED_ROWS:
        raise ValidationMaterializationError(f"Validation population changed: symbols={symbol_count} rows={row_count}")

    exact_backfill_ready=all(v==0 for v in backfill_missing.values())
    if exact_backfill_ready:
        status="READY"
        next_step="BUILD_M77_19_8_7_10_6_FROZEN_DEVELOPMENT_PREPROCESSOR_AND_VALIDATION_TARGET_MATERIALIZATION_AUTHORITY"
    else:
        status="BLOCKED_EXACT_8_4_3_PARTITION_PARAMETERIZATION_ADAPTER_REQUIRED"
        next_step="BUILD_M77_19_8_7_10_5_1_EXACT_8_4_3_PARTITION_PARAMETERIZATION_ADAPTER_AND_DEVELOPMENT_PARITY_GATE"

    coverage=[]
    for fid in REQUIRED_FEATURE_IDS:
        m=backfill_missing[fid];p=row_count-m
        coverage.append({"feature_id":fid,"present":p,"missing":m,"coverage_pct":p/row_count if row_count else None})

    report={
        "version":VERSION,"status":status,
        "parity_authority_sha256":sha256_file(pp),
        "continuity_authority_sha256":sha256_file(cp),
        "validation_authority_sha256":sha256_file(vp),
        "validation_symbol_count":symbol_count,
        "validation_row_count":row_count,
        "development_feature_schema_column_count":len(dev_schema),
        "required_backfill_feature_coverage":coverage,
        "exact_8_4_3_partition_parameterization_adapter_required":not exact_backfill_ready,
        "feature_formula_reimplementation_performed":False,
        "semantic_equivalent_rewrite_performed":False,
        "validation_feature_matrix_certified":exact_backfill_ready,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":next_step,
    }

    atomic_json(resolve(root,a.output_json),report)
    with resolve(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(coverage[0]));w.writeheader();w.writerows(coverage)

    print("=== M77.19.8.7.10.5 EXACT MAIN-REUSE VALIDATION FEATURE MATRIX MATERIALIZATION ===")
    print("status:",status)
    print("validation_symbol_count:",symbol_count)
    print("validation_row_count:",row_count)
    print("development_feature_schema_column_count:",len(dev_schema))
    for rec in coverage:
        print(f"{rec['feature_id']}: present={rec['present']} missing={rec['missing']} coverage_pct={rec['coverage_pct']}")
    print("exact_8_4_3_partition_parameterization_adapter_required:",not exact_backfill_ready)
    print("feature_formula_reimplementation_performed: False")
    print("semantic_equivalent_rewrite_performed: False")
    print("validation_feature_matrix_certified:",exact_backfill_ready)
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",next_step)
    print("report:",resolve(root,a.output_json))
    print("csv:",resolve(root,a.output_csv))
    print("output_root:",out_root)
    return 0

if __name__=="__main__":raise SystemExit(main())
