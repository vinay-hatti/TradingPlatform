#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.1-EXACT-PIT-VALIDATION-FEATURE-MATRIX-FROZEN-PREPROCESSOR-AUTHORITY-1.0"
EXPECTED_8710_VERSION="M77.19.8.7.10-AUTHORIZED-MODEL-FAMILY-VALIDATION-ONLY-EVALUATION-AUTHORITY-1.0"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"

class MaterializationError(RuntimeError):pass

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
def iter_jsonl_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise MaterializationError(f"{path}:{i}: invalid JSONL") from exc
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def write_jsonl_gz(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with gzip.open(tmp,"wt",encoding="utf-8") as f:
            for row in rows:f.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def get_path(obj,path):
    cur=obj
    for part in path.split("."):
        if not isinstance(cur,dict) or part not in cur:return None
        cur=cur[part]
    return cur
def scalar(v):
    if v is None:return None
    if isinstance(v,(bool,int,float,str)):return v
    return None
def flatten_base_features(values):
    out={}
    for fid,v in sorted((values or {}).items()):
        if fid=="F071":continue
        if isinstance(v,dict):
            if fid!="F070":continue
            for k,x in sorted(v.items()):
                if isinstance(x,(bool,int,float,str)) or x is None:out[f"{fid}__{k}"]=x
        elif isinstance(v,(bool,int,float,str)) or v is None:out[fid]=v
    return out
def build_structured(profile,gate):
    out={}
    for rec in gate.get("structured_columns") or []:
        fid=rec["feature_id"];source=rec["source_path"];col=rec["column_name"]
        payload=profile.get("timeframe_states") if fid=="F012" else profile.get("institutional_volume")
        out[col]=scalar(get_path(payload or {},source))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--validation-authority-json",default="reports/m77_19_8_7_10_authorized_model_family_validation_only_evaluation_authority.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-root",default="research_data/m77_19_8_7_10_1/validation_feature_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_1_exact_pit_validation_feature_matrix_frozen_preprocessor_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_1_validation_feature_schema_summary.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    vap=resolve(root,a.validation_authority_json);tgp=resolve(root,a.training_gate_json)
    va=load_json(vap);gate=load_json(tgp)
    if va.get("version")!=EXPECTED_8710_VERSION or va.get("status")!="READY":raise MaterializationError("M77.19.8.7.10 authority invalid")
    if va.get("validation_feature_materialization_authorized") is not True:raise MaterializationError("Validation feature materialization not authorized")
    if va.get("validation_feature_approximation_authorized") is not False:raise MaterializationError("approximation governance violated")
    if va.get("final_holdout_outcomes_open_authorized") is not False:raise MaterializationError("Final Holdout governance violated")

    dev_root=resolve(root,a.development_feature_root)
    replay_root=resolve(root,a.replay_root)/"weekly"/"profiles"
    daily_root=resolve(root,a.daily_materialization_root)
    out_root=resolve(root,a.output_root)
    out_root.mkdir(parents=True,exist_ok=True)

    dev_files={p.name[:-9]:p for p in dev_root.glob("*.jsonl.gz")}
    replay_files={p.name[:-9]:p for p in replay_root.glob("*.jsonl.gz")}
    daily_files={}
    for p in daily_root.rglob("*.daily.csv.gz"):
        symbol=p.name.split(".daily.csv.gz")[0]
        daily_files[symbol]=p
    if not dev_files:raise MaterializationError("Development feature matrix missing")
    if not replay_files:raise MaterializationError("PIT replay missing")

    # Infer exact Development feature-key schema from frozen materialization.
    dev_keys=None
    for symbol,path in sorted(dev_files.items()):
        first=next(iter_jsonl_gz(path),None)
        if first is None:continue
        keys=sorted((first.get("feature_values") or {}).keys())
        if dev_keys is None:dev_keys=keys
        elif keys!=dev_keys:raise MaterializationError("Development feature schema not uniform")
    if dev_keys is None:raise MaterializationError("could not infer Development schema")

    rows_total=0;symbols=0;schema_mismatch=0;missing_replay=0
    summaries=[]
    for symbol,rpath in sorted(replay_files.items()):
        selected=[]
        for rr in iter_jsonl_gz(rpath):
            d=str(rr.get("as_of") or "")[:10]
            if not (VALIDATION_START<=d<=VALIDATION_END):continue
            if rr.get("status")!="REPLAYED":continue
            profile=rr.get("profile")
            if not isinstance(profile,dict):raise MaterializationError(f"{symbol} {d}: missing profile")
            # Reuse the same top-level structured extraction contract used in Development.
            values={}
            # Direct fields expected from Development matrix are not recomputed heuristically.
            # Only values present explicitly in the PIT replay/profile are materialized.
            for fid in dev_keys:
                if fid in ("F012","F051","F071"):continue
                if fid.startswith("F070__"):
                    values[fid]=None
                else:
                    # Development backfill-derived scalar features are deliberately sourced from
                    # explicit PIT profile fields where available; absent values remain null.
                    values[fid]=None
            values.update(build_structured(profile,gate))
            # Preserve only frozen Development schema columns.
            ordered={k:values.get(k) for k in dev_keys}
            if sorted(ordered)!=dev_keys:schema_mismatch+=1
            selected.append({"symbol":symbol,"as_of":d,"feature_values":ordered,"status":"MATERIALIZED_PIT_VALIDATION"})
        if selected:
            write_jsonl_gz(out_root/f"{symbol}.jsonl.gz",selected)
            symbols+=1;rows_total+=len(selected)
            summaries.append({"symbol":symbol,"row_count":len(selected),"first_as_of":selected[0]["as_of"],"last_as_of":selected[-1]["as_of"]})

    # Because exact scalar backfill continuity cannot be proven merely by null-filling,
    # fail closed unless every frozen Development feature column is truly materializable.
    # This authority therefore reports the prerequisite gap rather than fabricating features.
    exact_scalar_feature_continuity=False
    report={
        "version":VERSION,
        "status":"BLOCKED_EXACT_VALIDATION_FEATURE_CONTINUITY_NOT_YET_PROVEN",
        "validation_authority_sha256":sha256_file(vap),
        "training_gate_sha256":sha256_file(tgp),
        "validation_window":{"start":VALIDATION_START,"end":VALIDATION_END},
        "development_feature_schema_column_count":len(dev_keys),
        "validation_profile_symbol_count_seen":symbols,
        "validation_profile_row_count_seen":rows_total,
        "validation_feature_schema_mismatch_count":schema_mismatch,
        "exact_scalar_feature_continuity_certified":False,
        "validation_feature_matrix_certified":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "validation_feature_approximation_performed":False,
        "development_preprocessor_refit_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "blocking_reason":"DEVELOPMENT_BACKFILL_FEATURES_REQUIRE_EXACT_2018_2022_SOURCE_RESOLUTION_AND_CANNOT_BE_NULL_FILLED_OR_APPROXIMATED",
        "next_step":"BUILD_M77_19_8_7_10_2_EXACT_VALIDATION_BACKFILL_SOURCE_RESOLVER_AND_FEATURE_CONTINUITY_AUTHORITY",
    }
    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    with oc.open("w",encoding="utf-8",newline="") as f:
        fields=["symbol","row_count","first_as_of","last_as_of"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(summaries)

    print("=== M77.19.8.7.10.1 EXACT PIT VALIDATION FEATURE MATRIX & FROZEN PREPROCESSOR AUTHORITY ===")
    print("status: BLOCKED_EXACT_VALIDATION_FEATURE_CONTINUITY_NOT_YET_PROVEN")
    print("development_feature_schema_column_count:",len(dev_keys))
    print("validation_profile_symbol_count_seen:",symbols)
    print("validation_profile_row_count_seen:",rows_total)
    print("exact_scalar_feature_continuity_certified: False")
    print("validation_feature_matrix_certified: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("validation_feature_approximation_performed: False")
    print("development_preprocessor_refit_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("blocking_reason: DEVELOPMENT_BACKFILL_FEATURES_REQUIRE_EXACT_2018_2022_SOURCE_RESOLUTION_AND_CANNOT_BE_NULL_FILLED_OR_APPROXIMATED")
    print("next_step: BUILD_M77_19_8_7_10_2_EXACT_VALIDATION_BACKFILL_SOURCE_RESOLVER_AND_FEATURE_CONTINUITY_AUTHORITY")
    print("report:",oj);print("csv:",oc)
    return 0

if __name__=="__main__":raise SystemExit(main())
