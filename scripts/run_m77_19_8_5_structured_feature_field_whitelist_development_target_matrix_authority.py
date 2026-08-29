#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,math,os,tempfile,re
from bisect import bisect_right
from collections import Counter
from pathlib import Path

VERSION="M77.19.8.5-STRUCTURED-FEATURE-FIELD-WHITELIST-DEVELOPMENT-TARGET-MATRIX-AUTHORITY-1.0"
EXPECTED_843_VERSION="M77.19.8.4.3-CERTIFIED-SOURCE-RESOLVER-DEVELOPMENT-FEATURE-BACKFILL-REPAIR-1.0"
EXPECTED_84_VERSION="M77.19.8.4-BLOCKED-FEATURE-SCHEMA-CENSUS-DEVELOPMENT-FEATURE-BACKFILL-AUTHORITY-1.0"
EXPECTED_83_VERSION="M77.19.8.3-BLOCKED-FEATURE-EXTRACTOR-AUTHORITY-DEVELOPMENT-TARGET-MATRIX-PREREGISTRATION-1.0"
DEV_END="2017-12-31"
VALIDATION_START="2018-01-01"
FINAL_HOLDOUT_START="2023-01-01"
HORIZONS=[5,10,20]
DATE_FIELD="session_date"
CLOSE_FIELD="close"
MODEL_SAFE_TYPES={"number","bool","string"}
PROHIBITED_TOKENS={
    "symbol","ticker","timestamp","snapshot","provider","hash","id","uuid",
    "future","outcome","target","validation","holdout","message","description",
}
PROHIBITED_SUBSTRINGS={
    "forward_return","future_return","target_return","validation_result",
    "holdout_result","explainability","warning","reason_text",
}

class AuthorityError(RuntimeError): pass

def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def load_json(path):
    with Path(path).open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root,raw):
    p=Path(raw).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def iter_jsonl_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise AuthorityError(f"{path}:{i}: invalid JSONL") from exc

def write_jsonl_gz(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with gzip.open(tmp,"wt",encoding="utf-8") as fh:
            for row in rows:fh.write(json.dumps(row,sort_keys=True,separators=(",",":"))+"\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def atomic_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def tokenize_path(path):
    toks=[]
    for part in str(path).split("."):
        toks.extend(t for t in re.split(r"[^A-Za-z0-9]+",part.lower()) if t)
    return toks

def safe_field(path,observed_types):
    lp=str(path).lower()
    toks=set(tokenize_path(path))
    if toks & PROHIBITED_TOKENS:
        return False,"PROHIBITED_PATH_TOKEN"
    if any(s in lp for s in PROHIBITED_SUBSTRINGS):
        return False,"PROHIBITED_PATH_SEMANTIC"
    non_null=sorted(t for t in set(observed_types) if t!="null")
    if not non_null:return False,"NULL_ONLY"
    if len(non_null)!=1:return False,"TYPE_CONFLICT"
    if non_null[0] not in MODEL_SAFE_TYPES:return False,"UNSAFE_TYPE"
    return True,"STRUCTURALLY_ELIGIBLE"

def load_daily_csv(path):
    rows=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as fh:
        rd=csv.DictReader(fh)
        fields=rd.fieldnames or []
        if DATE_FIELD not in fields or CLOSE_FIELD not in fields:
            raise AuthorityError(f"{path}: certified daily fields missing")
        for r in rd:
            d=str(r.get(DATE_FIELD) or "")[:10]
            try:c=float(r.get(CLOSE_FIELD))
            except Exception:continue
            if d and math.isfinite(c) and c>0:rows.append((d,c))
    rows.sort()
    return rows

def daily_file_map(root):
    out={}
    for p in sorted(root.rglob("*.daily.csv.gz")):
        sym=p.name[:-len(".daily.csv.gz")]
        if sym in out:raise AuthorityError(f"ambiguous daily source for {sym}")
        out[sym]=p
    return out

def exact_close_map(hist):
    out={}
    for d,c in hist:
        if d in out and abs(out[d]-c)>1e-12*max(1.0,abs(c),abs(out[d])):
            raise AuthorityError(f"conflicting close for {d}")
        out[d]=c
    return out

def spy_index(spy_dates,as_of):
    i=bisect_right(spy_dates,as_of)-1
    if i<0 or spy_dates[i]!=as_of:return None
    return i

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--backfill-authority-json",default="reports/m77_19_8_4_3_certified_source_resolver_development_feature_backfill_repair.json")
    ap.add_argument("--schema-census-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--extractor-authority-json",default="reports/m77_19_8_3_blocked_feature_extractor_authority_development_target_matrix_preregistration.json")
    ap.add_argument("--feature-matrix-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-root",default="research_data/m77_19_8_5/development_target_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_5_structured_feature_field_whitelist.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    bp=resolve(root,args.backfill_authority_json);sp=resolve(root,args.schema_census_json);ep=resolve(root,args.extractor_authority_json)
    fmroot=resolve(root,args.feature_matrix_root);dr=resolve(root,args.daily_materialization_root);outroot=resolve(root,args.output_root)
    ba=load_json(bp);sc=load_json(sp);ea=load_json(ep)

    if ba.get("version")!=EXPECTED_843_VERSION or ba.get("status")!="READY":raise AuthorityError("M77.19.8.4.3 authority invalid")
    if sc.get("version")!=EXPECTED_84_VERSION or sc.get("status")!="READY":raise AuthorityError("M77.19.8.4 authority invalid")
    if ea.get("version")!=EXPECTED_83_VERSION or ea.get("status")!="READY":raise AuthorityError("M77.19.8.3 authority invalid")
    if ba.get("materialized_symbol_count")!=524 or ba.get("materialized_row_count")!=303689:raise AuthorityError("Development authority mismatch")
    if ba.get("reference_price_vs_daily_close_mismatch_count")!=0:raise AuthorityError("reference parity mismatch")

    registry=[];whitelist={}
    for fid in ("F012","F051"):
        rows=((sc.get("schema_census") or {}).get(fid) or {}).get("scalar_leaf_paths") or []
        allowed=[]
        for r in rows:
            ok,reason=safe_field(r.get("path"),r.get("observed_types") or [])
            registry.append({
                "feature_id":fid,"path":r.get("path"),"observation_count":r.get("observation_count"),
                "observed_types":"|".join(r.get("observed_types") or []),"whitelisted":ok,"decision_reason":reason,
            })
            if ok:allowed.append(r.get("path"))
        whitelist[fid]=sorted(allowed)
    if not whitelist["F012"] or not whitelist["F051"]:raise AuthorityError("structured whitelist unexpectedly empty")

    tr=ea.get("target_preregistration") or {}
    if tr.get("horizons")!=HORIZONS:raise AuthorityError("target horizons mismatch")
    if tr.get("future_data_authorized_for_features") is not False:raise AuthorityError("future-feature governance mismatch")

    daily=daily_file_map(dr)
    if len(daily)!=602 or "SPY" not in daily:raise AuthorityError("602-symbol daily authority missing")
    spy_hist=load_daily_csv(daily["SPY"]);spy_dates=[d for d,_ in spy_hist];spy_close=exact_close_map(spy_hist)
    feature_files=sorted(fmroot.glob("*.jsonl.gz"))
    if len(feature_files)!=524:raise AuthorityError(f"expected 524 feature files, found {len(feature_files)}")

    maturity=Counter();labels=Counter();total=0;symbols=[]
    for ff in feature_files:
        symbol=ff.name[:-9]
        hist=load_daily_csv(daily[symbol]);closes=exact_close_map(hist)
        source_feature_sha=sha256_file(ff)
        out_rows=[]
        for frow in iter_jsonl_gz(ff):
            as_of=str(frow.get("as_of") or "")[:10]
            if not as_of or as_of>DEV_END:raise AuthorityError(f"{symbol}: non-Development feature row {as_of}")
            total+=1;base=closes.get(as_of);si=spy_index(spy_dates,as_of);targets={}
            for h in HORIZONS:
                rec={"horizon_sessions":h}
                if base is None or si is None:
                    rec.update(status="SOURCE_SESSION_MISSING",absolute_forward_return=None,market_relative_forward_return=None,direction_label=None,target_session=None)
                    maturity[(h,"SOURCE_SESSION_MISSING")]+=1;targets[str(h)]=rec;continue
                ti=si+h
                if ti>=len(spy_dates):
                    rec.update(status="NOT_MATURED",absolute_forward_return=None,market_relative_forward_return=None,direction_label=None,target_session=None)
                    maturity[(h,"NOT_MATURED")]+=1;targets[str(h)]=rec;continue
                td=spy_dates[ti]
                if td>=VALIDATION_START:
                    rec.update(status="PURGED_PARTITION_OVERLAP",absolute_forward_return=None,market_relative_forward_return=None,direction_label=None,target_session=td)
                    maturity[(h,"PURGED_PARTITION_OVERLAP")]+=1;targets[str(h)]=rec;continue
                end=closes.get(td)
                if end is None:
                    rec.update(status="SYMBOL_TARGET_SESSION_MISSING",absolute_forward_return=None,market_relative_forward_return=None,direction_label=None,target_session=td)
                    maturity[(h,"SYMBOL_TARGET_SESSION_MISSING")]+=1;targets[str(h)]=rec;continue
                abs_ret=end/base-1.0;spy_ret=spy_close[td]/spy_close[as_of]-1.0;rel=abs_ret-spy_ret
                lab="UP" if abs_ret>0 else "DOWN" if abs_ret<0 else "ZERO"
                rec.update(status="MATURED",absolute_forward_return=abs_ret,market_relative_forward_return=rel,direction_label=lab,target_session=td)
                maturity[(h,"MATURED")]+=1;labels[(h,lab)]+=1;targets[str(h)]=rec
            out_rows.append({"symbol":symbol,"as_of":as_of,"feature_source_sha256":source_feature_sha,"targets":targets})
        out=outroot/f"{symbol}.jsonl.gz";write_jsonl_gz(out,out_rows)
        symbols.append({"symbol":symbol,"row_count":len(out_rows),"output_file":str(out.relative_to(root)),"output_sha256":sha256_file(out),"source_feature_sha256":source_feature_sha,"source_daily_sha256":sha256_file(daily[symbol])})
    if total!=303689:raise AuthorityError(f"row count changed: {total}")

    hs={}
    for h in HORIZONS:
        hs[str(h)]={
            "matured":maturity[(h,"MATURED")],
            "purged_partition_overlap":maturity[(h,"PURGED_PARTITION_OVERLAP")],
            "not_matured":maturity[(h,"NOT_MATURED")],
            "source_session_missing":maturity[(h,"SOURCE_SESSION_MISSING")],
            "symbol_target_session_missing":maturity[(h,"SYMBOL_TARGET_SESSION_MISSING")],
            "direction_labels":{"UP":labels[(h,"UP")],"DOWN":labels[(h,"DOWN")],"ZERO":labels[(h,"ZERO")]},
        }

    report={
        "version":VERSION,"status":"READY",
        "backfill_authority_sha256":sha256_file(bp),"schema_census_authority_sha256":sha256_file(sp),"extractor_target_preregistration_sha256":sha256_file(ep),
        "structured_feature_whitelist":{
            "selection_basis":"DEVELOPMENT_SCHEMA_STRUCTURE_ONLY_NO_OUTCOMES",
            "F012_whitelisted_paths":whitelist["F012"],"F051_whitelisted_paths":whitelist["F051"],
            "F012_whitelisted_count":len(whitelist["F012"]),"F051_whitelisted_count":len(whitelist["F051"]),
            "F012_materialized_into_training_matrix":False,"F051_materialized_into_training_matrix":False,
            "whitelist_frozen_after_this_authority":True,
        },
        "target_matrix":{
            "partition":"DEVELOPMENT_ONLY","development_end":DEV_END,"validation_start":VALIDATION_START,
            "symbol_count":len(symbols),"feature_observation_count":total,"horizons":HORIZONS,"horizon_summary":hs,
            "future_bars_used_for_target_labeling_only":True,"future_bars_used_for_feature_construction":False,
            "partition_overlap_purged":True,"spy_session_calendar_authority":"FROZEN_M77_19_7_2_SPY_DAILY_CSV",
        },
        "symbols":symbols,
        "governance":{
            "development_outcomes_opened":True,"validation_feature_matrix_opened":False,"validation_outcomes_opened":False,
            "final_holdout_feature_matrix_opened":False,"final_holdout_outcomes_opened":False,
            "F071_materialized":False,"sector_relative_strength_still_blocked":True,
            "standardization_fit":False,"imputation_fit":False,"feature_selection_using_targets":False,
            "hyperparameter_search_performed":False,"model_training_performed":False,"model_scoring_performed":False,
            "calibration_performed":False,"production_model_change_authorized":False,"production_authority_effect":False,
        },
        "next_step":"BUILD_M77_19_8_6_STRUCTURED_FEATURE_MATERIALIZATION_AND_DEVELOPMENT_MODEL_TRAINING_PREREGISTRATION_GATE",
    }

    oj=resolve(root,args.output_json);oc=resolve(root,args.output_csv);atomic_json(oj,report)
    oc.parent.mkdir(parents=True,exist_ok=True)
    with oc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=["feature_id","path","observation_count","observed_types","whitelisted","decision_reason"]);w.writeheader();w.writerows(registry)

    print("=== M77.19.8.5 STRUCTURED FEATURE FIELD WHITELIST & DEVELOPMENT TARGET MATRIX AUTHORITY ===")
    print("status: READY")
    print("F012_whitelisted_count:",len(whitelist["F012"]))
    print("F051_whitelisted_count:",len(whitelist["F051"]))
    print("F012_materialized_into_training_matrix: False")
    print("F051_materialized_into_training_matrix: False")
    print("target_partition: DEVELOPMENT_ONLY")
    print("feature_observation_count:",total)
    for h in HORIZONS:
        s=hs[str(h)]
        print(f"horizon_{h}: matured={s['matured']} purged_partition_overlap={s['purged_partition_overlap']} source_session_missing={s['source_session_missing']} symbol_target_session_missing={s['symbol_target_session_missing']} labels={s['direction_labels']}")
    print("future_bars_used_for_target_labeling_only: True")
    print("future_bars_used_for_feature_construction: False")
    print("partition_overlap_purged: True")
    print("development_outcomes_opened: True")
    print("validation_outcomes_opened: False")
    print("final_holdout_outcomes_opened: False")
    print("F071_materialized: False")
    print("model_training_performed: False")
    print("production_authority_effect: False")
    print("next_step: BUILD_M77_19_8_6_STRUCTURED_FEATURE_MATERIALIZATION_AND_DEVELOPMENT_MODEL_TRAINING_PREREGISTRATION_GATE")
    print("report:",oj);print("csv:",oc);print("target_root:",outroot)
    return 0

if __name__=="__main__":raise SystemExit(main())
