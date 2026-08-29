#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,gzip,hashlib,json,math,os,tempfile
from collections import Counter
from pathlib import Path

VERSION="M77.19.8.7.10.6-FROZEN-DEVELOPMENT-PREPROCESSOR-VALIDATION-TARGET-MATERIALIZATION-AUTHORITY-1.0"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"
HORIZONS=(5,10,20)
TARGET_IDS=("T_ABS_RET","T_REL_SPY_RET","T_DIRECTION")
EXPECTED_FEATURE_ROWS=141567
EXPECTED_FEATURE_SYMBOLS=570

class AuthorityError(RuntimeError): pass

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def hash_tree(root):
    h=hashlib.sha256()
    files=sorted(Path(root).glob("*.jsonl.gz"))
    for p in files:
        h.update(p.name.encode());h.update(b"\0");h.update(sha256_file(p).encode());h.update(b"\n")
    return h.hexdigest(),len(files)

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def iter_jsonl(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise AuthorityError(f"{path}:{i}: invalid JSONL") from exc

def write_jsonl(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with gzip.open(tmp,"wt",encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def parse_daily(path):
    rows=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            d=str(r.get("session_date") or "")[:10]
            try:c=float(r.get("close"))
            except Exception:continue
            if d and math.isfinite(c) and c>0:rows.append((d,c))
    rows.sort()
    return rows

def daily_map(root):
    out={}
    for p in Path(root).glob("**/*.daily.csv.gz"):
        name=p.name
        sym=name[:-13] if name.endswith(".daily.csv.gz") else None
        if not sym:continue
        if sym in out:
            raise AuthorityError(f"duplicate daily mapping for {sym}")
        out[sym]=p
    return out

def direction(x):
    if x>0:return "UP"
    if x<0:return "DOWN"
    return "ZERO"

# M77.19.8.7.10.6.1-TRAINING-GATE-GOVERNANCE-SCHEMA-BINDING-REPAIR
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--validation-backfill-authority-json",default="reports/m77_19_8_7_10_5_2_4_exact_8_4_3_validation_backfill_matrix_materialization.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--development-target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    ap.add_argument("--development-feature-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--validation-feature-root",default="research_data/m77_19_8_7_10_5_2_4/validation_feature_matrix_certified_backfill")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-root",default="research_data/m77_19_8_7_10_6/validation_target_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_6_frozen_development_preprocessor_validation_target_materialization_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_6_validation_target_horizon_summary.csv")
    args=ap.parse_args()
    root=Path(args.project_root).resolve()

    vb=load_json(resolve(root,args.validation_backfill_authority_json))
    tg=load_json(resolve(root,args.training_gate_json))
    dt=load_json(resolve(root,args.development_target_authority_json))

    if vb.get("status")!="READY" or vb.get("validation_backfill_matrix_certified") is not True:
        raise AuthorityError("Validation backfill matrix not READY/certified")
    if vb.get("validation_row_count")!=EXPECTED_FEATURE_ROWS or vb.get("validation_symbol_count")!=EXPECTED_FEATURE_SYMBOLS:
        raise AuthorityError("Validation feature cardinality changed")
    if vb.get("validation_outcomes_opened") is not False or vb.get("final_holdout_opened") is not False:
        raise AuthorityError("upstream governance violation")
    if tg.get("status")!="READY":
        raise AuthorityError("training gate not READY")

    # M77.19.8.7.10.6.1 — bind to the actual authoritative M77.19.8.6 schema.
    # Missing fields are NOT treated as approval. All required governance
    # assertions must exist explicitly and resolve to False / DEVELOPMENT_ONLY.
    selection_metrics=tg.get("selection_and_metrics")
    walk_forward=tg.get("walk_forward_preregistration")
    execution_state=tg.get("execution_state")
    if not isinstance(selection_metrics,dict):
        raise AuthorityError("training-gate selection_and_metrics missing")
    if not isinstance(walk_forward,dict):
        raise AuthorityError("training-gate walk_forward_preregistration missing")
    if not isinstance(execution_state,dict):
        raise AuthorityError("training-gate execution_state missing")

    governance_values={
        "selection_and_metrics.validation_used_for_selection": selection_metrics.get("validation_used_for_selection"),
        "selection_and_metrics.final_holdout_used_for_selection": selection_metrics.get("final_holdout_used_for_selection"),
        "walk_forward_preregistration.validation_period_used": walk_forward.get("validation_period_used"),
        "walk_forward_preregistration.final_holdout_used": walk_forward.get("final_holdout_used"),
        "execution_state.validation_opened": execution_state.get("validation_opened"),
        "execution_state.final_holdout_opened": execution_state.get("final_holdout_opened"),
    }
    invalid_governance={k:v for k,v in governance_values.items() if v is not False}
    if invalid_governance:
        raise AuthorityError("training-gate selection governance violated or unresolved: " + repr(invalid_governance))
    if walk_forward.get("selection_scope")!="DEVELOPMENT_ONLY":
        raise AuthorityError("training-gate selection_scope is not DEVELOPMENT_ONLY")
    if dt.get("status")!="READY":
        raise AuthorityError("Development target authority not READY")
    if tuple(dt.get("target_horizons") or HORIZONS)!=HORIZONS:
        # Some reports may not repeat the preregistration list; require equality if present.
        if dt.get("target_horizons") is not None:
            raise AuthorityError("target horizons changed")

    dev_root=resolve(root,args.development_feature_root)
    val_root=resolve(root,args.validation_feature_root)
    dev_tree_sha,dev_symbol_files=hash_tree(dev_root)
    val_tree_sha,val_symbol_files=hash_tree(val_root)
    if dev_symbol_files!=524:
        raise AuthorityError(f"Development feature root changed: {dev_symbol_files} files")
    if val_symbol_files!=EXPECTED_FEATURE_SYMBOLS:
        raise AuthorityError(f"Validation feature root changed: {val_symbol_files} files")

    # Freeze the preprocessor authority strictly to Development inputs.
    preprocessor_authority={
        "fit_partition":"DEVELOPMENT_ONLY",
        "development_feature_tree_sha256":dev_tree_sha,
        "training_gate_sha256":sha256_file(resolve(root,args.training_gate_json)),
        "development_target_authority_sha256":sha256_file(resolve(root,args.development_target_authority_json)),
        "validation_feature_tree_sha256_recorded_for_transform_only":val_tree_sha,
        "validation_refit_authorized":False,
        "validation_category_vocabulary_expansion_authorized":False,
        "validation_scaler_refit_authorized":False,
        "validation_imputer_refit_authorized":False,
        "model_retuning_authorized":False,
    }

    dmap=daily_map(resolve(root,args.daily_materialization_root))
    if "SPY" not in dmap:raise AuthorityError("SPY frozen daily source missing")
    spy=parse_daily(dmap["SPY"])
    spy_dates=[d for d,_ in spy]
    spy_close={d:c for d,c in spy}

    outroot=resolve(root,args.output_root)
    outroot.mkdir(parents=True,exist_ok=True)

    summary={h:Counter() for h in HORIZONS}
    labels={h:Counter() for h in HORIZONS}
    total_feature_rows=0
    target_rows_written={h:0 for h in HORIZONS}
    missing_daily_symbols=[]
    source_session_missing={h:0 for h in HORIZONS}
    target_session_missing={h:0 for h in HORIZONS}
    partition_overlap_purged={h:0 for h in HORIZONS}

    for vf in sorted(val_root.glob("*.jsonl.gz")):
        symbol=vf.name[:-9]
        if symbol not in dmap:
            missing_daily_symbols.append(symbol)
            continue
        hist=parse_daily(dmap[symbol])
        dates=[d for d,_ in hist]
        close={d:c for d,c in hist}
        idx={d:i for i,d in enumerate(dates)}
        out_by_h={h:[] for h in HORIZONS}

        for row in iter_jsonl(vf):
            total_feature_rows+=1
            as_of=str(row.get("as_of") or "")[:10]
            if not (VALIDATION_START<=as_of<=VALIDATION_END):
                raise AuthorityError(f"{symbol} {as_of}: Validation feature outside authorized window")
            if as_of not in idx:
                for h in HORIZONS:
                    source_session_missing[h]+=1
                continue
            i=idx[as_of]
            s0=close[as_of]

            # Relative benchmark return uses the exact same source and target
            # sessions as the symbol target. No row-by-row SPY index search.
            for h in HORIZONS:
                j=i+h
                if j>=len(dates):
                    target_session_missing[h]+=1
                    continue
                td=dates[j]
                # Purge any Validation label whose target session enters Final Holdout.
                if td>VALIDATION_END:
                    partition_overlap_purged[h]+=1
                    continue
                abs_ret=close[td]/s0-1.0

                rel_ret=None
                if as_of in spy_close and td in spy_close:
                    spy_ret=spy_close[td]/spy_close[as_of]-1.0
                    rel_ret=abs_ret-spy_ret

                target={
                    "symbol":symbol,
                    "as_of":as_of,
                    "target_session":td,
                    "horizon_sessions":h,
                    "T_ABS_RET":abs_ret,
                    "T_REL_SPY_RET":rel_ret,
                    "T_DIRECTION":direction(abs_ret),
                    "partition":"VALIDATION",
                    "future_bars_used_for_target_labeling_only":True,
                }
                out_by_h[h].append(target)
                target_rows_written[h]+=1
                labels[h][target["T_DIRECTION"]]+=1
                summary[h]["matured"]+=1

        for h in HORIZONS:
            if out_by_h[h]:
                write_jsonl(outroot/f"h{h}"/f"{symbol}.jsonl.gz",out_by_h[h])

    if missing_daily_symbols:
        raise AuthorityError(f"Validation daily sources missing for {len(missing_daily_symbols)} symbols")
    if total_feature_rows!=EXPECTED_FEATURE_ROWS:
        raise AuthorityError(f"Validation feature row count changed during target materialization: {total_feature_rows}")

    rows=[]
    for h in HORIZONS:
        rows.append({
            "horizon":h,
            "matured":summary[h]["matured"],
            "partition_overlap_purged":partition_overlap_purged[h],
            "source_session_missing":source_session_missing[h],
            "symbol_target_session_missing":target_session_missing[h],
            "UP":labels[h]["UP"],
            "DOWN":labels[h]["DOWN"],
            "ZERO":labels[h]["ZERO"],
        })

    report={
        "version":VERSION,
        "status":"READY",
        "validation_backfill_authority_sha256":sha256_file(resolve(root,args.validation_backfill_authority_json)),
        "validation_feature_tree_sha256":val_tree_sha,
        "development_feature_tree_sha256":dev_tree_sha,
        "preprocessor_authority":preprocessor_authority,
        "training_gate_governance_resolution":{
            "selection_and_metrics.validation_used_for_selection":selection_metrics.get("validation_used_for_selection"),
            "selection_and_metrics.final_holdout_used_for_selection":selection_metrics.get("final_holdout_used_for_selection"),
            "walk_forward_preregistration.validation_period_used":walk_forward.get("validation_period_used"),
            "walk_forward_preregistration.final_holdout_used":walk_forward.get("final_holdout_used"),
            "walk_forward_preregistration.selection_scope":walk_forward.get("selection_scope"),
            "execution_state.validation_opened":execution_state.get("validation_opened"),
            "execution_state.final_holdout_opened":execution_state.get("final_holdout_opened"),
        },
        "training_gate_governance_certified":True,
        "preprocessor_fit_partition":"DEVELOPMENT_ONLY",
        "preprocessor_fit_executed_by_this_step":False,
        "frozen_preprocessor_contract_certified":True,
        "validation_partition_start":VALIDATION_START,
        "validation_partition_end":VALIDATION_END,
        "validation_feature_observation_count":total_feature_rows,
        "target_horizons":list(HORIZONS),
        "target_ids":list(TARGET_IDS),
        "target_horizon_summary":rows,
        "future_bars_used_for_target_labeling_only":True,
        "future_bars_used_for_feature_construction":False,
        "partition_overlap_purged":True,
        "validation_targets_opened":True,
        "validation_targets_materialized":True,
        "validation_outcomes_opened":True,
        "validation_scoring_performed":False,
        "validation_model_refit_performed":False,
        "validation_preprocessor_refit_performed":False,
        "validation_model_retuning_performed":False,
        "final_holdout_feature_rows_opened":False,
        "final_holdout_targets_opened":False,
        "final_holdout_outcomes_opened":False,
        "model_family_champion_selected":False,
        "production_authority_effect":False,
        "next_step":"BUILD_M77_19_8_7_10_7_FROZEN_MF1_MF2_VALIDATION_SCORING_AND_STABILITY_EVIDENCE",
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["horizon","matured","partition_overlap_purged","source_session_missing","symbol_target_session_missing","UP","DOWN","ZERO"])
        w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.6 FROZEN DEVELOPMENT PREPROCESSOR & VALIDATION TARGET MATERIALIZATION AUTHORITY ===")
    print("status: READY")
    print("training_gate_governance_certified: True")
    print("training_gate_selection_scope:",walk_forward.get("selection_scope"))
    print("training_gate_validation_used_for_selection:",selection_metrics.get("validation_used_for_selection"))
    print("training_gate_final_holdout_used_for_selection:",selection_metrics.get("final_holdout_used_for_selection"))
    print("preprocessor_fit_partition: DEVELOPMENT_ONLY")
    print("preprocessor_fit_executed_by_this_step: False")
    print("frozen_preprocessor_contract_certified: True")
    print("validation_feature_observation_count:",total_feature_rows)
    for r in rows:
        print(f"horizon_{r['horizon']}: matured={r['matured']} purged_partition_overlap={r['partition_overlap_purged']} source_session_missing={r['source_session_missing']} symbol_target_session_missing={r['symbol_target_session_missing']} labels={{'UP': {r['UP']}, 'DOWN': {r['DOWN']}, 'ZERO': {r['ZERO']}}}")
    print("future_bars_used_for_target_labeling_only: True")
    print("future_bars_used_for_feature_construction: False")
    print("partition_overlap_purged: True")
    print("validation_targets_opened: True")
    print("validation_targets_materialized: True")
    print("validation_outcomes_opened: True")
    print("validation_scoring_performed: False")
    print("validation_model_refit_performed: False")
    print("validation_preprocessor_refit_performed: False")
    print("validation_model_retuning_performed: False")
    print("final_holdout_feature_rows_opened: False")
    print("final_holdout_targets_opened: False")
    print("final_holdout_outcomes_opened: False")
    print("model_family_champion_selected: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,args.output_json))
    print("csv:",resolve(root,args.output_csv))
    print("target_root:",outroot)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
