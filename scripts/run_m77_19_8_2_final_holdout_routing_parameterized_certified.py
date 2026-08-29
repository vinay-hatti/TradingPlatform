#!/usr/bin/env python3
"""
M77.19.8.2 — Development-Only Feature Matrix Materialization & Schema Validation

Materializes the first Prospective Edge Intelligence feature matrix using ONLY
point-in-time replay rows whose as_of <= 2017-12-31.

Important:
- no Validation rows are materialized;
- no Final Holdout rows are materialized;
- no outcome/target data is read;
- no model is trained or scored;
- all 27 frozen feature IDs are represented;
- features that require an unbuilt extractor/authority remain NULL with explicit
  missingness rather than being approximated;
- structured payloads are not flattened opportunistically.
"""
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, os, tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

VERSION="M77.19.8.2-DEVELOPMENT-ONLY-FEATURE-MATRIX-MATERIALIZATION-SCHEMA-VALIDATION-1.0"
EXPECTED_FEATURE_VERSION="M77.19.8.1-POINT-IN-TIME-PROSPECTIVE-EDGE-FEATURE-AUTHORITY-1.0"
EXPECTED_REPLAY_SHA="0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
DEV_END="2017-12-31"
ACTIVE_PARTITION_START=""
ACTIVE_PARTITION_END=DEV_END
ACTIVE_PARTITION_LABEL="DEVELOPMENT"
VALIDATION_START="2018-01-01"
FINAL_HOLDOUT_START="2023-01-01"

DIRECT_FEATURES={
    "F001": lambda row,p,ctx,state: row.get("overall_score"),
    "F002": lambda row,p,ctx,state: p.get("confidence"),
    "F003": lambda row,p,ctx,state: p.get("direction"),
    "F010": lambda row,p,ctx,state: p.get("alignment_score"),
    "F011": lambda row,p,ctx,state: p.get("primary_timeframe"),
    "F032": lambda row,p,ctx,state: len(p.get("support_levels") or []),
    "F033": lambda row,p,ctx,state: len(p.get("resistance_levels") or []),
    "F040": lambda row,p,ctx,state: (p.get("breakout") or {}).get("state"),
    "F050": lambda row,p,ctx,state: (p.get("participation") or {}).get("state"),
    "F060": lambda row,p,ctx,state: ctx.get("breadth_bullish_fraction"),
    "F061": lambda row,p,ctx,state: ctx.get("breadth_bearish_fraction"),
    "F062": lambda row,p,ctx,state: ctx.get("spy_return_13w"),
    "F063": lambda row,p,ctx,state: ctx.get("spy_return_26w"),
    "F064": lambda row,p,ctx,state: ctx.get("spy_realized_vol_26w_annualized"),
    "F065": lambda row,p,ctx,state: ctx.get("spy_drawdown_from_52w_peak"),
    "F090": lambda row,p,ctx,state: state["direction_age"],
    "F091": lambda row,p,ctx,state: state["direction_changed"],
}

# These frozen IDs intentionally remain unavailable until their extractor or
# prerequisite PIT authority is separately certified. No approximation is made.
AUTHORITY_BLOCKED_FEATURES={
    "F012":"STRUCTURED_TIMEFRAME_FIELD_FLATTENING_NOT_YET_PREREGISTERED",
    "F020":"NATIVE_ATR_FIELD_PATH_NOT_YET_CERTIFIED",
    "F021":"REFERENCE_PRICE_AND_ATR_EXTRACTOR_NOT_YET_CERTIFIED",
    "F030":"REFERENCE_PRICE_LEVEL_DISTANCE_EXTRACTOR_NOT_YET_CERTIFIED",
    "F031":"REFERENCE_PRICE_LEVEL_DISTANCE_EXTRACTOR_NOT_YET_CERTIFIED",
    "F051":"STRUCTURED_INSTITUTIONAL_VOLUME_FIELD_FLATTENING_NOT_YET_PREREGISTERED",
    "F070":"SYMBOL_TRAILING_RETURN_EXTRACTOR_NOT_YET_CERTIFIED",
    "F071":"PIT_SECTOR_BENCHMARK_AUTHORITY_NOT_AVAILABLE",
    "F080":"SYMBOL_52W_PREFIX_EXTREME_EXTRACTOR_NOT_YET_CERTIFIED",
    "F081":"SYMBOL_52W_PREFIX_EXTREME_EXTRACTOR_NOT_YET_CERTIFIED",
}

class MatrixError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    """Canonicalize project-relative paths against --project-root.

    Never preserve a relative path merely because it exists relative to the
    process working directory. That breaks provenance paths and relative_to(root).
    """
    p=Path(raw).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (root/p).resolve()

def iter_jsonl_gz(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise MatrixError(f"{path}:{i}: invalid JSON") from exc

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def scalar(v):
    if v in ("",None):return None
    if isinstance(v,(bool,int,float,str)):return v
    return None

def write_symbol_matrix(out:Path, rows:list[dict[str,Any]]):
    out.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=out.name+".",suffix=".tmp",dir=out.parent);os.close(fd)
    try:
        with gzip.open(tmp,"wt",encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")
        os.replace(tmp,out)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--partition-start",default="")
    ap.add_argument("--partition-end",default="2017-12-31")
    ap.add_argument("--partition-label",default="DEVELOPMENT")
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--feature-authority-json",default="reports/m77_19_8_1_point_in_time_prospective_edge_feature_authority.json")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--output-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_2_development_only_feature_matrix_materialization_schema_validation.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_2_feature_matrix_schema_summary.csv")
    args=ap.parse_args()
    globals()["ACTIVE_PARTITION_START"]=args.partition_start
    globals()["ACTIVE_PARTITION_END"]=args.partition_end
    globals()["ACTIVE_PARTITION_LABEL"]=args.partition_label

    root=Path(args.project_root).resolve()
    fp=resolve(root,args.feature_authority_json)
    rp=resolve(root,args.replay_authority_json)
    rr=resolve(root,args.replay_root)
    cp=resolve(root,args.context_csv)
    outroot=resolve(root,args.output_root)

    fa=load_json(fp); replay=load_json(rp)
    if fa.get("version")!=EXPECTED_FEATURE_VERSION or fa.get("status")!="READY":
        raise MatrixError("M77.19.8.1 feature authority invalid")
    if sha256_file(rp)!=EXPECTED_REPLAY_SHA:
        raise MatrixError("replay authority SHA mismatch")
    features=fa.get("features") or []
    feature_ids=[x["id"] for x in features]
    if len(feature_ids)!=27 or len(set(feature_ids))!=27:
        raise MatrixError("expected exactly 27 unique frozen feature IDs")
    if set(DIRECT_FEATURES)|set(AUTHORITY_BLOCKED_FEATURES)!=set(feature_ids):
        raise MatrixError("materializer feature coverage differs from frozen 27-feature authority")
    if not rr.exists():
        raise MatrixError(f"replay root missing: {rr}")

    # Development PIT market context only. Validation rows are observed only to
    # prove they are skipped and are never joined to materialized rows.
    context={}
    validation_context_rows_seen_and_skipped=0
    final_holdout_context_rows_seen=0
    with cp.open("r",encoding="utf-8",newline="") as fh:
        for r in csv.DictReader(fh):
            as_of=str(r["as_of"])[:10]
            if ACTIVE_PARTITION_LABEL=="FINAL_HOLDOUT":
                if ACTIVE_PARTITION_START<=as_of<=ACTIVE_PARTITION_END and r.get("partition")=="FINAL_HOLDOUT":
                    context[as_of]=r
            elif as_of>=FINAL_HOLDOUT_START:
                final_holdout_context_rows_seen+=1
            elif ACTIVE_PARTITION_LABEL=="DEVELOPMENT":
                if as_of<=ACTIVE_PARTITION_END and r.get("partition")==ACTIVE_PARTITION_LABEL:
                    context[as_of]=r
                elif VALIDATION_START<=as_of<FINAL_HOLDOUT_START:
                    validation_context_rows_seen_and_skipped+=1
            elif ACTIVE_PARTITION_LABEL=="VALIDATION":
                if ACTIVE_PARTITION_START<=as_of<=ACTIVE_PARTITION_END and r.get("partition")==ACTIVE_PARTITION_LABEL:
                    context[as_of]=r
            else:
                raise MatrixError(f"unsupported active partition label: {ACTIVE_PARTITION_LABEL}")
    if final_holdout_context_rows_seen and ACTIVE_PARTITION_LABEL!="FINAL_HOLDOUT":
        raise MatrixError("Final Holdout context unexpectedly present")

    files=sorted((rr/"weekly"/"profiles").glob("*.jsonl.gz"))
    if len(files)!=602:
        raise MatrixError(f"expected 602 replay profile files, found {len(files)}")

    outroot.mkdir(parents=True,exist_ok=True)
    symbol_summaries=[]
    global_missing=Counter()
    global_present=Counter()
    total_rows=0
    validation_replay_rows_seen_and_skipped=0
    final_holdout_replay_rows_seen_and_skipped=0
    native_not_eligible_skipped=0

    for path in files:
        symbol=path.name[:-9]  # strip .jsonl.gz
        materialized=[]
        prev_direction=None
        direction_age=0
        replayed_seen=0
        for row in iter_jsonl_gz(path):
            as_of=str(row.get("as_of") or "")[:10]
            status=row.get("status")
            if ACTIVE_PARTITION_LABEL=="FINAL_HOLDOUT":
                if not as_of or as_of<ACTIVE_PARTITION_START or as_of>ACTIVE_PARTITION_END:
                    continue
            elif as_of>=FINAL_HOLDOUT_START:
                final_holdout_replay_rows_seen_and_skipped+=1
                continue
            if ACTIVE_PARTITION_LABEL=="DEVELOPMENT":
                if VALIDATION_START<=as_of<FINAL_HOLDOUT_START:
                    validation_replay_rows_seen_and_skipped+=1
                    continue
                if not as_of or as_of>ACTIVE_PARTITION_END:
                    continue
            elif ACTIVE_PARTITION_LABEL=="VALIDATION":
                if not as_of or as_of<ACTIVE_PARTITION_START or as_of>ACTIVE_PARTITION_END:
                    continue
            elif ACTIVE_PARTITION_LABEL=="FINAL_HOLDOUT":
                pass
            else:
                raise MatrixError(f"unsupported active partition label: {ACTIVE_PARTITION_LABEL}")
            if status!="REPLAYED":
                native_not_eligible_skipped+=1
                continue
            p=row.get("profile")
            if not isinstance(p,dict):
                raise MatrixError(f"{symbol} {as_of}: REPLAYED row missing full profile")
            replayed_seen+=1
            cur=p.get("direction")
            changed=(prev_direction is not None and cur!=prev_direction)
            direction_age=1 if prev_direction is None or changed else direction_age+1
            state={"direction_age":direction_age,"direction_changed":changed}
            prev_direction=cur

            ctx=context.get(as_of) or {}
            values={}
            missing={}
            reasons={}
            for fid in feature_ids:
                if fid in DIRECT_FEATURES:
                    v=scalar(DIRECT_FEATURES[fid](row,p,ctx,state))
                    values[fid]=v
                    is_missing=v is None
                    missing[fid]=is_missing
                    if is_missing:
                        reasons[fid]="SOURCE_VALUE_MISSING_AT_AS_OF"
                        global_missing[fid]+=1
                    else:
                        global_present[fid]+=1
                else:
                    values[fid]=None
                    missing[fid]=True
                    reasons[fid]=AUTHORITY_BLOCKED_FEATURES[fid]
                    global_missing[fid]+=1

            materialized.append({
                "symbol":symbol,
                "as_of":as_of,
                "cadence":"WEEKLY",
                "source_semantic_hash":row.get("semantic_hash"),
                "feature_values":values,
                "feature_missing":missing,
                "feature_missing_reason":reasons,
            })

        if materialized:
            out=outroot/f"{symbol}.jsonl.gz"
            write_symbol_matrix(out,materialized)
            symbol_summaries.append({
                "symbol":symbol,
                "row_count":len(materialized),
                "first_as_of":materialized[0]["as_of"],
                "last_as_of":materialized[-1]["as_of"],
                "output_file":str(out.relative_to(root)),
                "output_sha256":sha256_file(out),
            })
            total_rows+=len(materialized)

    schema_rows=[]
    fmap={x["id"]:x for x in features}
    for fid in feature_ids:
        schema_rows.append({
            "feature_id":fid,
            "feature_name":fmap[fid]["name"],
            "domain":fmap[fid]["domain"],
            "materialization_state":"MATERIALIZED_WHEN_SOURCE_PRESENT" if fid in DIRECT_FEATURES else "AUTHORITY_BLOCKED_NULL_WITH_MISSINGNESS",
            "present_count":global_present[fid],
            "missing_count":global_missing[fid],
            "blocked_reason":AUTHORITY_BLOCKED_FEATURES.get(fid,""),
        })

    report={
        "version":VERSION,
        "status":"READY",
        "feature_authority_sha256":sha256_file(fp),
        "replay_authority_sha256":EXPECTED_REPLAY_SHA,
        "context_csv_sha256":sha256_file(cp),
        "development_end":DEV_END,
        "active_partition_start":ACTIVE_PARTITION_START,
        "active_partition_end":ACTIVE_PARTITION_END,
        "active_partition_label":ACTIVE_PARTITION_LABEL,
        "feature_count":len(feature_ids),
        "direct_materializable_feature_count":len(DIRECT_FEATURES),
        "authority_blocked_feature_count":len(AUTHORITY_BLOCKED_FEATURES),
        "materialized_symbol_count":len(symbol_summaries),
        "materialized_row_count":total_rows,
        "symbols":symbol_summaries,
        "schema_summary":schema_rows,
        "scope_protection":{
            "development_only":ACTIVE_PARTITION_LABEL=="DEVELOPMENT",
            "outcome_or_target_data_read":False,
            "validation_context_rows_seen_and_skipped":validation_context_rows_seen_and_skipped,
            "validation_replay_rows_seen_and_skipped":validation_replay_rows_seen_and_skipped,
            "final_holdout_context_rows_seen":final_holdout_context_rows_seen,
            "final_holdout_replay_rows_seen_and_skipped":final_holdout_replay_rows_seen_and_skipped,
            "validation_matrix_materialized":False,
            "final_holdout_matrix_materialized":False,
        },
        "schema_governance":{
            "all_27_feature_ids_represented":True,
            "blocked_features_approximated":False,
            "structured_payloads_flattened_opportunistically":False,
            "missingness_explicit_per_feature_per_row":True,
            "symbol_identity_in_feature_values":False,
            "closed_hypothesis_identity_in_feature_values":False,
            "future_information_in_feature_values":False,
        },
        "execution_state":{
            "development_feature_matrix_materialized":True,
            "training_targets_materialized":False,
            "standardization_parameters_fit":False,
            "categorical_vocabulary_fit":False,
            "imputation_parameters_fit":False,
            "feature_selection_performed":False,
            "models_trained":False,
            "models_scored":False,
            "validation_opened_for_model_scoring":False,
            "final_holdout_opened":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_8_3_BLOCKED_FEATURE_EXTRACTOR_AUTHORITY_AND_DEVELOPMENT_TARGET_MATRIX_PREREGISTRATION",
    }

    oj=Path(args.output_json);oc=Path(args.output_csv)
    if not oj.is_absolute():oj=root/oj
    if not oc.is_absolute():oc=root/oc
    atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=list(schema_rows[0].keys()))
        w.writeheader();w.writerows(schema_rows)

    print("=== M77.19.8.2 DEVELOPMENT-ONLY FEATURE MATRIX MATERIALIZATION & SCHEMA VALIDATION ===")
    print("status: READY")
    print("development_end:",DEV_END)
    print("feature_count:",len(feature_ids))
    print("direct_materializable_feature_count:",len(DIRECT_FEATURES))
    print("authority_blocked_feature_count:",len(AUTHORITY_BLOCKED_FEATURES))
    print("materialized_symbol_count:",len(symbol_summaries))
    print("materialized_row_count:",total_rows)
    print("outcome_or_target_data_read: False")
    print("validation_context_rows_seen_and_skipped:",validation_context_rows_seen_and_skipped)
    print("validation_replay_rows_seen_and_skipped:",validation_replay_rows_seen_and_skipped)
    print("final_holdout_context_rows_seen:",final_holdout_context_rows_seen)
    print("validation_matrix_materialized: False")
    print("final_holdout_matrix_materialized: False")
    print("blocked_features_approximated: False")
    print("training_targets_materialized: False")
    print("models_trained: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_3_BLOCKED_FEATURE_EXTRACTOR_AUTHORITY_AND_DEVELOPMENT_TARGET_MATRIX_PREREGISTRATION")
    print("report:",oj)
    print("csv:",oc)
    print("output_root:",outroot)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
