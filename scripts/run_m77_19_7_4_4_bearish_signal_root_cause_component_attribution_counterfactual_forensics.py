#!/usr/bin/env python3
"""
M77.19.7.4.4 — Bearish Signal Root-Cause Component Attribution &
Counterfactual Forensics

Research-only diagnostic analysis over immutable M77.19.7.3.1 point-in-time
profiles and M77.19.7.4.1 realized outcomes.

Purpose:
- contrast correct vs incorrect BEARISH / STRONG_BEARISH observations;
- attribute outcome differences to frozen native component states;
- report conditional hit rates, return economics, prevalence, risk differences,
  and simple effect-size diagnostics;
- inspect predeclared component interactions;
- perform descriptive counterfactual contrasts without fitting a model.

Strict prohibitions:
- no Polygon API
- no database or price_history
- no profile recomputation
- no production imports
- no threshold search / optimization
- no parameter or calibrator fitting
- no classifier training
- no automatic inversion of bearish signals
- no production authority effect
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import statistics
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

VERSION = "M77.19.7.4.4.3-NATIVE-NOT-ELIGIBLE-ROW-HANDLING-REPAIR-1.0"
EXPECTED_REPLAY_AUTHORITY_SHA256 = "0d2e684363e51ddf4de4df81d0978e03c5c5c0a6d5604f77b438494dd36c87b3"
EXPECTED_REPLAY_AUTHORITY_VERSION = "M77.19.7.3.1.1-FULL-PROFILE-RESUME-INTEGRITY-REPAIR-1.0"
EXPECTED_OUTCOME_AUTHORITY_VERSION = "M77.19.7.4.1.2-REPAIRED-FULL-PROFILE-AUTHORITY-REPIN-1.0"
EXPECTED_OUTCOME_AUTHORITY_SHA256 = "d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"
EXPECTED_SYMBOL_COUNT = 602
EXPECTED_PROFILE_COUNT = 556283
FIXED_HORIZONS = (5,10,20)
BEARISH_CLASSES = ("BEARISH","STRONG_BEARISH")
FIXED_ERAS = (
    ("2003-2007",2003,2007),
    ("2008-2012",2008,2012),
    ("2013-2017",2013,2017),
    ("2018-2022",2018,2022),
    ("2023-2026",2023,2026),
)

# Predeclared native component domains. Paths are not fitted or selected by
# realized performance. Missing paths are retained as MISSING.
COMPONENT_PATHS = (
    "primary_timeframe",
    "alignment_score",
    "confidence",
    "categories.primary",
    "context.market_regime",
    "context.regime",
    "structure.state",
    "structure.trend",
    "breakout.state",
    "participation.state",
    "participation.score",
    "participation.conviction",
    "participation.deterioration_risk",
    "institutional_volume.state",
    "institutional_volume.score",
    "scores.trend",
    "scores.momentum",
    "scores.structure",
    "scores.participation",
    "scores.confidence",
    "timeframe_states.1d.direction",
    "timeframe_states.1d.confidence",
    "timeframe_states.1w.direction",
    "timeframe_states.1w.confidence",
    "timeframe_states.1mo.direction",
    "timeframe_states.1mo.confidence",
    "decision_intelligence.decision",
    "decision_intelligence.state",
    "trade_plan.certification.status",
)

# Predeclared interactions chosen from architecture, not outcome performance.
INTERACTION_PATHS = (
    ("timeframe_states.1d.direction","timeframe_states.1w.direction"),
    ("timeframe_states.1w.direction","timeframe_states.1mo.direction"),
    ("timeframe_states.1d.direction","timeframe_states.1mo.direction"),
    ("structure.state","participation.state"),
    ("structure.state","breakout.state"),
    ("participation.state","institutional_volume.state"),
)

class ForensicError(RuntimeError): pass

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def resolve_project_path(project_root: Path, raw: str|Path) -> Path:
    p=Path(raw)
    if p.exists(): return p
    for anchor in ("research_data","reports","data"):
        if anchor in p.parts:
            i=p.parts.index(anchor)
            q=project_root.joinpath(*p.parts[i:])
            if q.exists(): return q
    if not p.is_absolute():
        q=project_root/p
        if q.exists(): return q
    return p

def load_json(path: Path) -> dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:
        return json.load(fh)

def read_jsonl(path: Path) -> Iterable[dict[str,Any]]:
    opener=gzip.open if path.suffix==".gz" else open
    with opener(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip(): continue
            try: yield json.loads(line)
            except Exception as exc:
                raise ForensicError(f"{path}:{i}: invalid JSONL") from exc

def outcome_rows(path: Path) -> Iterable[dict[str,Any]]:
    yield from read_jsonl(path)

def profile_rows(path: Path) -> Iterable[dict[str,Any]]:
    yield from read_jsonl(path)

def _native_profile_signature(v: Any) -> bool:
    return isinstance(v, dict) and "direction" in v and "timeframe_states" in v


def _decode_top_level_json_object(v: Any) -> dict[str, Any] | None:
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not (s.startswith("{") and s.endswith("}")):
        return None
    try:
        decoded = json.loads(s)
    except Exception:
        return None
    return decoded if isinstance(decoded, dict) else None


def extract_profile_payload(row: dict[str,Any]) -> dict[str,Any]:
    """Require the exact M77.19.7.3.1.1 top-level profile contract."""
    profile=row.get("profile")
    if not _native_profile_signature(profile):
        raise ForensicError(
            "M77.19.7.3.1.1 full-profile authority violation: "
            "REPLAYED row missing valid top-level profile payload"
        )
    return profile

def row_as_of(row: dict[str,Any], profile: dict[str,Any]) -> str:
    for key in ("as_of","prediction_date","snapshot_date"):
        if row.get(key): return str(row[key])[:10]
    ts=profile.get("snapshot_timestamp")
    if ts: return str(ts)[:10]
    raise ForensicError("replay profile row missing as_of/snapshot date")

def get_path(obj: Any, path: str) -> Any:
    cur=obj
    for part in path.split("."):
        if not isinstance(cur,dict) or part not in cur:
            return None
        cur=cur[part]
    return cur

def canonical_state(v: Any) -> str:
    if v is None: return "MISSING"
    if isinstance(v,bool): return "TRUE" if v else "FALSE"
    if isinstance(v,(int,float)) and not isinstance(v,bool):
        if not math.isfinite(float(v)): return "NONFINITE"
        # Descriptive fixed native-score bands, not optimized.
        x=float(v)
        if 0 <= x <= 100:
            if x < 20: return "0-20"
            if x < 40: return "20-40"
            if x < 60: return "40-60"
            if x < 80: return "60-80"
            return "80-100"
        return f"NUMERIC:{round(x,4)}"
    s=str(v).strip().upper()
    return s if s else "EMPTY"

def era_label(year:int)->str:
    for label,a,b in FIXED_ERAS:
        if a<=year<=b:return label
    return "OUTSIDE_FIXED_ERAS"

def new_acc()->dict[str,Any]:
    return {
        "count":0,"correct":0,"incorrect":0,
        "directional_return_sum":0.0,
        "directional_returns":[],
    }

def add(acc:dict[str,Any], forward_return:float)->None:
    # Bearish directional return is positive when underlying falls.
    d=-float(forward_return)
    acc["count"]+=1
    acc["directional_return_sum"]+=d
    acc["directional_returns"].append(d)
    if d>0: acc["correct"]+=1
    else: acc["incorrect"]+=1

def ratio(n,d): return None if not d else n/d

def finalize(acc:dict[str,Any])->dict[str,Any]:
    xs=acc["directional_returns"]
    return {
        "count":acc["count"],
        "correct":acc["correct"],
        "incorrect":acc["incorrect"],
        "accuracy":ratio(acc["correct"],acc["count"]),
        "mean_directional_return":(
            acc["directional_return_sum"]/acc["count"] if acc["count"] else None
        ),
        "median_directional_return":statistics.median(xs) if xs else None,
    }

def risk_difference(a_correct,a_total,b_correct,b_total)->float|None:
    if not a_total or not b_total:return None
    return a_correct/a_total-b_correct/b_total

def odds_ratio(a_correct,a_total,b_correct,b_total)->float|None:
    # Haldane-Anscombe correction for zero cells; descriptive only.
    a=a_correct+0.5
    b=(a_total-a_correct)+0.5
    c=b_correct+0.5
    d=(b_total-b_correct)+0.5
    return (a/b)/(c/d)

def validate_authorities(project_root:Path,outcome_path:Path,replay_path:Path):
    if sha256_file(outcome_path) != EXPECTED_OUTCOME_AUTHORITY_SHA256:
        raise ForensicError("M77.19.7.4.1.2 outcome authority SHA mismatch")
    outcome=load_json(outcome_path)
    replay=load_json(replay_path)
    if outcome.get("version")!=EXPECTED_OUTCOME_AUTHORITY_VERSION:
        raise ForensicError(f"unexpected outcome authority version {outcome.get('version')!r}")
    if outcome.get("status")!="READY": raise ForensicError("outcome authority not READY")
    if outcome.get("successful_symbol_evaluation_count")!=EXPECTED_SYMBOL_COUNT:
        raise ForensicError("outcome symbol count mismatch")
    if outcome.get("aggregate_replayed_profile_count")!=EXPECTED_PROFILE_COUNT:
        raise ForensicError("outcome profile count mismatch")
    if sha256_file(replay_path)!=EXPECTED_REPLAY_AUTHORITY_SHA256:
        raise ForensicError("M77.19.7.3.1 replay authority SHA mismatch")
    if replay.get("version")!=EXPECTED_REPLAY_AUTHORITY_VERSION:
        raise ForensicError("unexpected replay authority version")
    if replay.get("status")!="READY": raise ForensicError("replay authority not READY")
    if replay.get("successful_symbol_cadence_replay_count")!=EXPECTED_SYMBOL_COUNT:
        raise ForensicError("replay symbol count mismatch")
    if replay.get("failed_symbol_cadence_replay_count")!=0:
        raise ForensicError("replay authority has failures")
    return outcome,replay

def build_replay_index(project_root:Path,replay:dict[str,Any])->dict[str,dict[str,Any]]:
    out={}
    for row in replay.get("symbols") or []:
        if row.get("cadence")!="WEEKLY" or row.get("status")!="REPLAYED_POINT_IN_TIME":
            continue
        sym=str(row.get("symbol") or "").strip()
        if not sym or sym in out: raise ForensicError(f"invalid/duplicate replay symbol {sym!r}")
        result=resolve_project_path(project_root,row.get("result_file") or "")
        if not result.is_file(): raise ForensicError(f"{sym}: replay result file missing: {result}")
        if sha256_file(result)!=row.get("result_sha256"):
            raise ForensicError(f"{sym}: replay result SHA mismatch")
        out[sym]=row
    if len(out)!=EXPECTED_SYMBOL_COUNT:
        raise ForensicError(f"replay index count {len(out)} != {EXPECTED_SYMBOL_COUNT}")
    return out

def build_profile_map(project_root:Path,replay_meta:dict[str,Any])->dict[str,dict[str,Any]]:
    p=resolve_project_path(project_root,replay_meta["result_file"])
    out={}
    replayed_rows=0
    not_eligible_rows=0
    for row in profile_rows(p):
        status=row.get("status")
        if status == "NOT_ELIGIBLE_NATIVE":
            # M77.19.7.3.1.1 explicitly permits metadata-only rows here.
            # They cannot participate in bearish component attribution because
            # no native profile was produced.
            not_eligible_rows += 1
            continue
        if status != "REPLAYED":
            raise ForensicError(
                f"{replay_meta['symbol']}: unexpected replay row status {status!r}"
            )
        replayed_rows += 1
        profile=extract_profile_payload(row)
        d=row_as_of(row,profile)
        if d in out:
            raise ForensicError(f"{replay_meta['symbol']}: duplicate replay as_of {d}")
        out[d]=profile

    expected_replayed=int(replay_meta.get("replayed_profile_count") or 0)
    expected_not_eligible=int(replay_meta.get("native_not_eligible_count") or 0)
    if expected_replayed and replayed_rows != expected_replayed:
        raise ForensicError(
            f"{replay_meta['symbol']}: replayed row count mismatch "
            f"{replayed_rows} != {expected_replayed}"
        )
    if expected_not_eligible and not_eligible_rows != expected_not_eligible:
        raise ForensicError(
            f"{replay_meta['symbol']}: native-not-eligible row count mismatch "
            f"{not_eligible_rows} != {expected_not_eligible}"
        )
    return out

def component_summary(
    state_accs:dict[str,dict[str,Any]],
    overall:dict[str,Any],
)->dict[str,Any]:
    out={}
    for state,acc in sorted(state_accs.items()):
        f=finalize(acc)
        out[state]={
            **f,
            "prevalence":ratio(f["count"],overall["count"]),
            "accuracy_risk_difference_vs_all_bearish":(
                None if f["accuracy"] is None or overall["accuracy"] is None
                else f["accuracy"]-overall["accuracy"]
            ),
            "mean_return_difference_vs_all_bearish":(
                None if f["mean_directional_return"] is None or overall["mean_directional_return"] is None
                else f["mean_directional_return"]-overall["mean_directional_return"]
            ),
            "odds_ratio_correct_vs_all_other_bearish":odds_ratio(
                f["correct"],f["count"],
                overall["correct"]-f["correct"],
                overall["count"]-f["count"],
            ) if overall["count"]>f["count"] else None,
        }
    return out

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent)
    os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_4_bearish_signal_root_cause_component_attribution_counterfactual_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_4_bearish_component_state_evidence.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    outcome_path=resolve_project_path(root,args.outcome_authority_json)
    replay_path=resolve_project_path(root,args.replay_authority_json)
    outcome,replay=validate_authorities(root,outcome_path,replay_path)
    replay_index=build_replay_index(root,replay)

    # symbol -> outcome metadata
    oms={str(x["symbol"]):x for x in outcome.get("symbols") or []}
    if len(oms)!=EXPECTED_SYMBOL_COUNT: raise ForensicError("outcome symbol metadata count mismatch")

    overall={h:new_acc() for h in FIXED_HORIZONS}
    by_class={c:{h:new_acc() for h in FIXED_HORIZONS} for c in BEARISH_CLASSES}
    by_era=defaultdict(lambda:{h:new_acc() for h in FIXED_HORIZONS})
    comp={path:defaultdict(lambda:{h:new_acc() for h in FIXED_HORIZONS}) for path in COMPONENT_PATHS}
    interactions={
        "|".join(paths):defaultdict(lambda:{h:new_acc() for h in FIXED_HORIZONS})
        for paths in INTERACTION_PATHS
    }
    missing_profile_join=0
    bearish_observation_count=0

    for symbol in sorted(oms):
        om=oms[symbol]
        rm=replay_index.get(symbol)
        if rm is None: raise ForensicError(f"{symbol}: missing replay authority row")
        if om.get("source_data_sha256")!=rm.get("source_data_sha256"):
            raise ForensicError(f"{symbol}: source SHA mismatch 7.4.1 vs 7.3.1")
        profile_map=build_profile_map(root,rm)
        op=resolve_project_path(root,om["outcome_file"])
        if not op.is_file(): raise ForensicError(f"{symbol}: outcome file missing")
        if sha256_file(op)!=om.get("outcome_sha256"):
            raise ForensicError(f"{symbol}: outcome file SHA mismatch")
        for row in outcome_rows(op):
            native=str(row.get("native_direction") or row.get("direction") or "").upper()
            if native not in BEARISH_CLASSES: continue
            bearish_observation_count+=1
            as_of=str(row["as_of"])[:10]
            profile=profile_map.get(as_of)
            if profile is None:
                missing_profile_join+=1
                continue
            profile_direction=str(profile.get("direction") or "").upper()
            if profile_direction!=native:
                raise ForensicError(
                    f"{symbol} {as_of}: outcome/replay native direction mismatch "
                    f"{native} != {profile_direction}"
                )
            era=era_label(dt.date.fromisoformat(as_of).year)
            states={p:canonical_state(get_path(profile,p)) for p in COMPONENT_PATHS}
            inter_states={
                "|".join(paths):" || ".join(states[p] for p in paths)
                for paths in INTERACTION_PATHS
            }
            for h in FIXED_HORIZONS:
                o=row["outcomes"][str(h)]
                if o.get("status")!="MATURED": continue
                ret=float(o["forward_return"])
                add(overall[h],ret)
                add(by_class[native][h],ret)
                add(by_era[era][h],ret)
                for p,state in states.items(): add(comp[p][state][h],ret)
                for key,state in inter_states.items(): add(interactions[key][state][h],ret)

    if missing_profile_join:
        raise ForensicError(
            f"bearish outcome -> replay profile join failures: {missing_profile_join}"
        )

    f_overall={str(h):finalize(overall[h]) for h in FIXED_HORIZONS}
    f_class={c:{str(h):finalize(by_class[c][h]) for h in FIXED_HORIZONS} for c in BEARISH_CLASSES}
    f_era={e:{str(h):finalize(v[h]) for h in FIXED_HORIZONS} for e,v in sorted(by_era.items())}

    components={}
    for p in COMPONENT_PATHS:
        components[p]={}
        for h in FIXED_HORIZONS:
            states={s:accs[h] for s,accs in comp[p].items()}
            components[p][str(h)]=component_summary(states,f_overall[str(h)])

    interaction_evidence={}
    for key,state_map in interactions.items():
        interaction_evidence[key]={}
        for h in FIXED_HORIZONS:
            states={s:accs[h] for s,accs in state_map.items()}
            interaction_evidence[key][str(h)]=component_summary(states,f_overall[str(h)])

    # Counterfactual contrasts are descriptive matched-state contrasts:
    # which states are overrepresented in incorrect vs correct bearish outcomes.
    counterfactual={}
    for h in FIXED_HORIZONS:
        rows=[]
        for p in COMPONENT_PATHS:
            for state,e in components[p][str(h)].items():
                if e["count"]<2: continue
                rows.append({
                    "component_path":p,
                    "state":state,
                    "count":e["count"],
                    "accuracy":e["accuracy"],
                    "accuracy_risk_difference_vs_all_bearish":e["accuracy_risk_difference_vs_all_bearish"],
                    "mean_directional_return":e["mean_directional_return"],
                    "mean_return_difference_vs_all_bearish":e["mean_return_difference_vs_all_bearish"],
                    "odds_ratio_correct_vs_all_other_bearish":e["odds_ratio_correct_vs_all_other_bearish"],
                })
        counterfactual[str(h)]={
            "worst_accuracy_states":sorted(
                rows,key=lambda x:(1 if x["accuracy"] is None else 0, x["accuracy"] if x["accuracy"] is not None else 9, -x["count"])
            )[:50],
            "worst_mean_directional_return_states":sorted(
                rows,key=lambda x:(1 if x["mean_directional_return"] is None else 0, x["mean_directional_return"] if x["mean_directional_return"] is not None else 9, -x["count"])
            )[:50],
            "best_accuracy_states":sorted(
                rows,key=lambda x:(-1 if x["accuracy"] is None else 0, -(x["accuracy"] if x["accuracy"] is not None else -9), -x["count"])
            )[:50],
            "descriptive_only":True,
            "no_counterfactual_model_fitted":True,
        }

    report={
        "version":VERSION,
        "status":"READY",
        "replay_authority_sha256":EXPECTED_REPLAY_AUTHORITY_SHA256,
        "outcome_authority_sha256":sha256_file(outcome_path),
        "successful_symbol_count":EXPECTED_SYMBOL_COUNT,
        "bearish_observation_count":bearish_observation_count,
        "fixed_horizons_sessions":list(FIXED_HORIZONS),
        "bearish_classes":list(BEARISH_CLASSES),
        "overall_bearish_evidence":f_overall,
        "bearish_class_evidence":f_class,
        "era_evidence":f_era,
        "component_evidence":components,
        "predeclared_interaction_evidence":interaction_evidence,
        "descriptive_counterfactual_contrasts":counterfactual,
        "governance":{
            "database_access":"NONE",
            "polygon_api_queried":False,
            "price_history_table_used":False,
            "profile_recomputation_performed":False,
            "profile_payload_resolution":"M77_19_7_3_1_1_EXACT_TOP_LEVEL_PROFILE",
            "recursive_profile_field_guessing":False,
            "json_string_top_level_profile_supported":False,
            "metadata_only_replay_row_accepted":False,
            "metadata_only_not_eligible_native_row_accepted":True,
            "not_eligible_native_rows_skipped_before_profile_extraction":True,
            "production_package_imported":False,
            "threshold_search_or_optimization":False,
            "parameter_fitting":False,
            "calibrator_fitting":False,
            "classifier_training":False,
            "automatic_bearish_signal_inversion":False,
            "component_paths_predeclared":True,
            "interaction_paths_predeclared":True,
            "outcome_based_component_selection":False,
            "production_authority_effect":False,
            "production_model_change_authorized":False,
        },
        "decision_gate":{
            "bearish_root_cause_certified":False,
            "production_bearish_semantic_change_authorized":False,
            "next_step":"REVIEW_M77_19_7_4_4_COMPONENT_ATTRIBUTION_BEFORE_ANY_BEARISH_SEMANTIC_CHANGE",
        },
    }
    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)

    outc.parent.mkdir(parents=True,exist_ok=True)
    with outc.open("w",newline="",encoding="utf-8") as fh:
        fields=["component_path","state","horizon_sessions","count","accuracy",
                "accuracy_risk_difference_vs_all_bearish","mean_directional_return",
                "mean_return_difference_vs_all_bearish","odds_ratio_correct_vs_all_other_bearish"]
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader()
        for p in COMPONENT_PATHS:
            for h in FIXED_HORIZONS:
                for state,e in sorted(components[p][str(h)].items()):
                    w.writerow({"component_path":p,"state":state,"horizon_sessions":h,
                                **{k:e.get(k) for k in fields[3:]}})

    print("=== M77.19.7.4.4 BEARISH SIGNAL ROOT-CAUSE COMPONENT ATTRIBUTION & COUNTERFACTUAL FORENSICS ===")
    print()
    print("status: READY")
    print(f"successful_symbol_count: {EXPECTED_SYMBOL_COUNT}")
    print(f"bearish_observation_count: {bearish_observation_count}")
    for h in FIXED_HORIZONS:
        print(f"horizon_{h}_all_bearish: {f_overall[str(h)]}")
        for c in BEARISH_CLASSES:
            print(f"horizon_{h}_{c}: {f_class[c][str(h)]}")
        worst=counterfactual[str(h)]["worst_mean_directional_return_states"][:10]
        print(f"horizon_{h}_worst_component_states_by_mean_directional_return:")
        for x in worst:
            print(" ",x)
    print("classifier_training: False")
    print("automatic_bearish_signal_inversion: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_4_COMPONENT_ATTRIBUTION_BEFORE_ANY_BEARISH_SEMANTIC_CHANGE")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
