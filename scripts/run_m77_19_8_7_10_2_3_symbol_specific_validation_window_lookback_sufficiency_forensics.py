#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,os,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.2.3-SYMBOL-SPECIFIC-VALIDATION-WINDOW-LOOKBACK-SUFFICIENCY-FORENSICS-1.0"
VALIDATION_START="2018-01-01"
VALIDATION_END="2022-12-31"
# Frozen feature set requires up to 52-week location features. Use a conservative
# 260-session prior-history requirement; this does not change any feature formula.
REQUIRED_PRIOR_SESSIONS=260

class ForensicError(RuntimeError):pass

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
            except Exception as exc:raise ForensicError(f"{path}:{i}: invalid JSONL") from exc

def read_daily_sessions(path):
    sessions=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f)
        fields=r.fieldnames or []
        if "session_date" not in fields or "close" not in fields:
            raise ForensicError(f"{path}: certified daily schema missing")
        for row in r:
            d=str(row.get("session_date") or "")[:10]
            if d:sessions.append(d)
    if not sessions:raise ForensicError(f"{path}: no daily sessions")
    return sorted(set(sessions))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--continuity-json",default="reports/m77_19_8_7_10_2_exact_validation_backfill_source_resolver_feature_continuity_authority.json")
    ap.add_argument("--continuity-csv",default="reports/m77_19_8_7_10_2_validation_source_continuity_registry.csv")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_2_3_symbol_specific_validation_window_lookback_sufficiency_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_2_3_symbol_window_sufficiency_evidence.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    cp=resolve(root,a.continuity_json);cc=resolve(root,a.continuity_csv)
    cont=load_json(cp)
    if cont.get("status")!="BLOCKED_SOURCE_CONTINUITY":
        raise ForensicError("10.2 must be BLOCKED_SOURCE_CONTINUITY")
    if int(cont.get("validation_daily_window_failure_symbol_count",-1))!=38:
        raise ForensicError("expected exactly 38 global-window failures from 10.2")
    if cont.get("validation_outcomes_opened") is not False or cont.get("final_holdout_opened") is not False:
        raise ForensicError("partition governance violated")

    flagged=set()
    with cc.open("r",encoding="utf-8",newline="") as f:
        for row in csv.DictReader(f):
            if str(row.get("daily_validation_window_covered")).lower() not in ("true","1","yes"):
                flagged.add(row["symbol"])
    if len(flagged)!=38:
        raise ForensicError(f"continuity CSV flagged {len(flagged)} symbols, expected 38")

    replay_dir=resolve(root,a.replay_root)/"weekly"/"profiles"
    daily_root=resolve(root,a.daily_materialization_root)
    daily_files={}
    for p in daily_root.rglob("*.daily.csv.gz"):
        sym=p.name[:-13] if p.name.endswith(".daily.csv.gz") else p.stem
        daily_files.setdefault(sym,[]).append(p)

    rows=[]
    classifications={}
    actual_source_insufficient=[]
    global_only_false_positive=[]
    for symbol in sorted(flagged):
        rp=replay_dir/f"{symbol}.jsonl.gz"
        if not rp.exists():raise ForensicError(f"{symbol}: replay file missing")
        obs=[]
        for r in iter_jsonl_gz(rp):
            d=str(r.get("as_of") or "")[:10]
            if VALIDATION_START<=d<=VALIDATION_END and r.get("status")=="REPLAYED":
                obs.append(d)
        if not obs:raise ForensicError(f"{symbol}: no Validation replay observations")
        obs=sorted(obs)
        first_obs,last_obs=obs[0],obs[-1]

        candidates=daily_files.get(symbol,[])
        if len(candidates)!=1:
            candidates=[p for p in daily_root.rglob("*.daily.csv.gz") if p.name.startswith(symbol+".")]
        if len(candidates)!=1:
            raise ForensicError(f"{symbol}: daily resolver ambiguity count={len(candidates)}")
        sessions=read_daily_sessions(candidates[0])
        first_daily,last_daily=sessions[0],sessions[-1]

        # Locate the first Validation observation in the frozen symbol session history.
        # Required prior data are session-count based, not calendar-year based.
        prior=[d for d in sessions if d<first_obs]
        through_last=[d for d in sessions if d<=last_obs]
        first_obs_present=first_obs in sessions
        last_obs_present=last_obs in sessions
        prior_count=len(prior)
        has_required_prior=prior_count>=REQUIRED_PRIOR_SESSIONS
        covers_actual_observation_window=(
            first_daily<=first_obs and last_daily>=last_obs and
            first_obs_present and last_obs_present
        )
        exact_symbol_window_sufficient=bool(covers_actual_observation_window and has_required_prior)

        starts_after_global=first_daily>VALIDATION_START
        ends_before_global=last_daily<VALIDATION_END
        starts_after_first_obs=first_daily>first_obs
        ends_before_last_obs=last_daily<last_obs

        if exact_symbol_window_sufficient:
            classification="GLOBAL_WINDOW_FALSE_POSITIVE_SYMBOL_SPECIFIC_HISTORY_SUFFICIENT"
            global_only_false_positive.append(symbol)
        elif starts_after_first_obs or not first_obs_present:
            classification="ACTUAL_VALIDATION_START_COVERAGE_INSUFFICIENT"
            actual_source_insufficient.append(symbol)
        elif ends_before_last_obs or not last_obs_present:
            classification="ACTUAL_VALIDATION_END_COVERAGE_INSUFFICIENT"
            actual_source_insufficient.append(symbol)
        elif not has_required_prior:
            classification="PRIOR_LOOKBACK_INSUFFICIENT_FOR_52W_FEATURES"
            actual_source_insufficient.append(symbol)
        else:
            classification="UNRESOLVED_SOURCE_INSUFFICIENCY"
            actual_source_insufficient.append(symbol)

        classifications[classification]=classifications.get(classification,0)+1
        rows.append({
            "symbol":symbol,
            "classification":classification,
            "first_validation_observation":first_obs,
            "last_validation_observation":last_obs,
            "validation_observation_count":len(obs),
            "first_daily_session":first_daily,
            "last_daily_session":last_daily,
            "prior_daily_session_count_before_first_validation_observation":prior_count,
            "required_prior_sessions":REQUIRED_PRIOR_SESSIONS,
            "first_validation_observation_present_in_daily":first_obs_present,
            "last_validation_observation_present_in_daily":last_obs_present,
            "covers_actual_observation_window":covers_actual_observation_window,
            "has_required_prior_sessions":has_required_prior,
            "exact_symbol_window_sufficient":exact_symbol_window_sufficient,
            "starts_after_global_validation_start":starts_after_global,
            "ends_before_global_validation_end":ends_before_global,
        })

    report={
        "version":VERSION,
        "status":"READY",
        "continuity_authority_sha256":sha256_file(cp),
        "global_window_failure_symbol_count":len(flagged),
        "required_prior_sessions_for_forensics":REQUIRED_PRIOR_SESSIONS,
        "required_prior_sessions_basis":"CONSERVATIVE_52_WEEK_FEATURE_LOOKBACK_SUFFICIENCY_FORENSIC_GATE",
        "classification_counts":classifications,
        "global_window_false_positive_symbol_count":len(global_only_false_positive),
        "actual_source_insufficient_symbol_count":len(actual_source_insufficient),
        "global_window_false_positive_symbols":global_only_false_positive,
        "actual_source_insufficient_symbols":actual_source_insufficient,
        "symbol_specific_history_windows_preserved":True,
        "global_2018_2022_daily_coverage_required_for_every_symbol":False,
        "feature_formula_changed":False,
        "validation_feature_materialization_performed":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":(
            "BUILD_M77_19_8_7_10_2_4_SYMBOL_SPECIFIC_SOURCE_CONTINUITY_GATE_REPAIR"
            if not actual_source_insufficient else
            "REVIEW_ACTUAL_SOURCE_INSUFFICIENT_SYMBOLS_BEFORE_ANY_CONTINUITY_GATE_REPAIR"
        ),
    }

    oj=resolve(root,a.output_json);oc=resolve(root,a.output_csv);atomic_json(oj,report)
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

    print("=== M77.19.8.7.10.2.3 SYMBOL-SPECIFIC VALIDATION WINDOW & LOOKBACK SUFFICIENCY FORENSICS ===")
    print("status: READY")
    print("global_window_failure_symbol_count:",len(flagged))
    print("classification_counts:",classifications)
    print("global_window_false_positive_symbol_count:",len(global_only_false_positive))
    print("actual_source_insufficient_symbol_count:",len(actual_source_insufficient))
    print("actual_source_insufficient_symbols:",actual_source_insufficient)
    print("symbol_specific_history_windows_preserved: True")
    print("global_2018_2022_daily_coverage_required_for_every_symbol: False")
    print("feature_formula_changed: False")
    print("validation_feature_materialization_performed: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",oj);print("csv:",oc)
    return 0

if __name__=="__main__":raise SystemExit(main())
