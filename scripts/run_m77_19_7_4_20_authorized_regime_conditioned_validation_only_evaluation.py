#!/usr/bin/env python3
"""
M77.19.7.4.20 — Authorized Regime-Conditioned Validation-Only Evaluation

Scores ONLY the scopes authorized by M77.19.7.4.19:
- H4 >=10% structural room + RC1 DOWNTREND_HIGH_VOL
- H4 5-10% structural room + RC2 BEAR_MARKET_WEAK_BREADTH
at horizons 5,10,20.

Validation window: 2018-01-01 .. 2022-12-31.
Development is not rescored.
Final Holdout >= 2023-01-01 remains sealed.
"""
from __future__ import annotations

import argparse, csv, gzip, hashlib, json, math, os, statistics, tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION="M77.19.7.4.20-AUTHORIZED-REGIME-CONDITIONED-VALIDATION-ONLY-EVALUATION-1.0"
EXPECTED_GATE_VERSION="M77.19.7.4.19-REGIME-CONDITIONED-CANDIDATE-ADVANCEMENT-REDUNDANCY-GATE-1.0"
EXPECTED_REGIME_VERSION="M77.19.7.4.17-REGIME-THRESHOLD-COMBINATION-PREREGISTRATION-AUTHORITY-1.0"
EXPECTED_CONTEXT_VERSION="M77.19.7.4.16-PIT-REGIME-CONTEXT-MATERIALIZATION-AUTHORITY-1.0"
EXPECTED_OUTCOME_SHA="d8c8ea6fd2a6412d3b2898f87fa1e3f19ba6968b112eb100998c81ac2bb07775"

VAL_START="2018-01-01"
VAL_END="2022-12-31"
FINAL_HOLDOUT_START="2023-01-01"
MIN_VALIDATION_COUNT=300

EXPECTED_SCOPE={
    "RC_H4_GE10_DOWNTREND_HIGH_VOL":{
        "candidate_id":"H4_ROOM_PCT_GE_10PCT",
        "regime_id":"RC1_DOWNTREND_HIGH_VOL",
        "horizons":[5,10,20],
        "concept":"TREND_PLUS_VOLATILITY_STRESS",
    },
    "RC_H4_5_10_BEAR_MARKET_WEAK_BREADTH":{
        "candidate_id":"H4_ROOM_PCT_5_10PCT",
        "regime_id":"RC2_BEAR_MARKET_WEAK_BREADTH",
        "horizons":[5,10,20],
        "concept":"BEAR_MARKET_PLUS_BREADTH_STRESS",
    },
}

class ValidationError(RuntimeError): pass

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda:fh.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def load_json(path:Path)->dict[str,Any]:
    with path.open("r",encoding="utf-8") as fh:return json.load(fh)

def resolve(root:Path, raw:str|Path)->Path:
    p=Path(raw)
    if p.exists():return p
    q=root/p
    return q if q.exists() else p

def iter_jsonl(path:Path)->Iterable[dict[str,Any]]:
    with gzip.open(path,"rt",encoding="utf-8") as fh:
        for i,line in enumerate(fh,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise ValidationError(f"{path}:{i}: invalid JSONL") from exc

def stats(xs:list[float])->dict[str,Any]:
    if not xs:return {"count":0,"accuracy":None,"mean":None,"median":None}
    return {
        "count":len(xs),
        "accuracy":sum(x>0 for x in xs)/len(xs),
        "mean":statistics.fmean(xs),
        "median":statistics.median(xs),
    }

def classify_regimes(ctx:Mapping[str,Any], thresholds:Mapping[str,Any])->dict[str,bool]:
    def f(k):
        v=ctx.get(k)
        return None if v in (None,"") else float(v)
    vol=f("spy_realized_vol_26w_annualized")
    r13=f("spy_return_13w")
    r26=f("spy_return_26w")
    dd=f("spy_drawdown_from_52w_peak")
    bear_breadth=f("breadth_bearish_fraction")
    bull_breadth=f("breadth_bullish_fraction")
    spy_dir=str(ctx.get("spy_direction") or "").upper()

    high_vol=vol is not None and vol>=float(thresholds["VOLATILITY"]["normal_to_high"])
    downtrend=(r13 is not None and r26 is not None and r13<0 and r26<0
               and spy_dir in ("BEARISH","STRONG_BEARISH"))
    bear_market=dd is not None and dd<=float(thresholds["BEAR_MARKET_CONTEXT"]["correction_to_bear"])
    weak_breadth=(bear_breadth is not None and bull_breadth is not None
                  and bear_breadth>=float(thresholds["BREADTH_REGIME"]["bearish_high_threshold"])
                  and bull_breadth<float(thresholds["BREADTH_REGIME"]["bullish_high_threshold"]))

    return {
        "RC1_DOWNTREND_HIGH_VOL":downtrend and high_vol,
        "RC2_BEAR_MARKET_WEAK_BREADTH":bear_market and weak_breadth,
    }

def atomic_json(path:Path,payload:Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent);os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as fh:
            json.dump(payload,fh,indent=2,sort_keys=True);fh.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--advancement-gate-json",default="reports/m77_19_7_4_19_regime_conditioned_candidate_advancement_redundancy_gate.json")
    ap.add_argument("--regime-authority-json",default="reports/m77_19_7_4_17_regime_threshold_and_combination_preregistration_authority.json")
    ap.add_argument("--context-authority-json",default="reports/m77_19_7_4_16_point_in_time_regime_context_materialization_authority.json")
    ap.add_argument("--context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--h4-authority-json",default="reports/m77_19_7_4_10_h4_point_in_time_structural_downside_room_materialization_authority.json")
    ap.add_argument("--outcome-authority-json",default="reports/m77_19_7_4_symbol_specific_historical_outcome_calibration_evaluation.json")
    ap.add_argument("--output-json",default="reports/m77_19_7_4_20_authorized_regime_conditioned_validation_only_evaluation.json")
    ap.add_argument("--output-csv",default="reports/m77_19_7_4_20_validation_regime_candidate_evidence.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    gp=resolve(root,args.advancement_gate_json)
    rp=resolve(root,args.regime_authority_json)
    cp=resolve(root,args.context_authority_json)
    cc=resolve(root,args.context_csv)
    hp=resolve(root,args.h4_authority_json)
    op=resolve(root,args.outcome_authority_json)

    gate=load_json(gp);reg=load_json(rp);ctxauth=load_json(cp);h4=load_json(hp);outcome=load_json(op)
    if gate.get("version")!=EXPECTED_GATE_VERSION or gate.get("status")!="READY":
        raise ValidationError("7.4.19 advancement gate invalid")
    if reg.get("version")!=EXPECTED_REGIME_VERSION or reg.get("status")!="READY":
        raise ValidationError("7.4.17 regime authority invalid")
    if ctxauth.get("version")!=EXPECTED_CONTEXT_VERSION or ctxauth.get("status")!="READY":
        raise ValidationError("7.4.16 context authority invalid")
    if sha256_file(op)!=EXPECTED_OUTCOME_SHA:
        raise ValidationError("outcome authority SHA mismatch")

    actual=gate.get("authorized_validation_scope") or {}
    if set(actual)!=set(EXPECTED_SCOPE):
        raise ValidationError("authorized validation scope differs from frozen expected scope")
    for name,spec in EXPECTED_SCOPE.items():
        a=actual[name]
        for k in ("candidate_id","regime_id","horizons","concept"):
            if a.get(k)!=spec[k]:
                raise ValidationError(f"{name}: frozen scope field {k} differs")

    if gate.get("validation_gate_contract",{}).get("final_holdout_remains_sealed") is not True:
        raise ValidationError("Final Holdout not sealed by upstream gate")

    thresholds=reg.get("thresholds") or {}

    # Validation-only context.
    context={}
    validation_context_rows_seen=0
    development_context_rows_skipped=0
    final_holdout_context_rows_seen=0
    with cc.open("r",encoding="utf-8",newline="") as fh:
        for row in csv.DictReader(fh):
            as_of=row["as_of"][:10]
            if row.get("partition")=="DEVELOPMENT":
                development_context_rows_skipped+=1
                continue
            if as_of>=FINAL_HOLDOUT_START:
                final_holdout_context_rows_seen+=1
                continue
            if row.get("partition")!="VALIDATION" or not (VAL_START<=as_of<=VAL_END):
                continue
            validation_context_rows_seen+=1
            context[as_of]=classify_regimes(row,thresholds)

    if validation_context_rows_seen!=ctxauth.get("validation_context_row_count"):
        raise ValidationError("Validation context count mismatch")
    if final_holdout_context_rows_seen!=0:
        raise ValidationError("Final Holdout context unexpectedly present")

    # Validation-only H4 geometry.
    geom={}
    development_geometry_rows_skipped=0
    final_holdout_geometry_rows_skipped=0
    for sm in h4.get("symbols") or []:
        symbol=str(sm["symbol"])
        f=resolve(root,sm["materialization_file"])
        if sha256_file(f)!=sm["materialization_sha256"]:
            raise ValidationError(f"{symbol}: H4 materialization SHA mismatch")
        for row in iter_jsonl(f):
            part=row.get("partition")
            as_of=str(row["as_of"])[:10]
            if part=="DEVELOPMENT":
                development_geometry_rows_skipped+=1
                continue
            if part=="FINAL_HOLDOUT" or as_of>=FINAL_HOLDOUT_START:
                final_holdout_geometry_rows_skipped+=1
                continue
            if part!="VALIDATION" or not (VAL_START<=as_of<=VAL_END):
                continue
            b=row.get("nearest_structural_room_pct_bin")
            if b in ("GE_10PCT","5_10PCT"):
                geom[(symbol,as_of)]=b

    memberships={name:set() for name in EXPECTED_SCOPE}
    returns={name:{5:[],10:[],20:[]} for name in EXPECTED_SCOPE}
    unconditioned={
        "H4_ROOM_PCT_GE_10PCT":{5:[],10:[],20:[]},
        "H4_ROOM_PCT_5_10PCT":{5:[],10:[],20:[]},
    }
    final_holdout_outcome_rows_seen_and_skipped=0
    development_outcome_rows_skipped=0

    oms={str(x["symbol"]):x for x in outcome.get("symbols") or []}
    for symbol,sm in oms.items():
        of=resolve(root,sm["outcome_file"])
        if sha256_file(of)!=sm["outcome_sha256"]:
            raise ValidationError(f"{symbol}: outcome SHA mismatch")
        for row in iter_jsonl(of):
            as_of=str(row["as_of"])[:10]
            if as_of<= "2017-12-31":
                development_outcome_rows_skipped+=1
                continue
            if as_of>=FINAL_HOLDOUT_START:
                final_holdout_outcome_rows_seen_and_skipped+=1
                continue
            if not (VAL_START<=as_of<=VAL_END):
                continue
            if as_of not in context:continue
            b=geom.get((symbol,as_of))
            if b is None:continue

            cid="H4_ROOM_PCT_GE_10PCT" if b=="GE_10PCT" else "H4_ROOM_PCT_5_10PCT"
            for h in (5,10,20):
                o=(row.get("outcomes") or {}).get(str(h)) or {}
                if o.get("status")!="MATURED":continue
                y=-float(o["forward_return"])
                unconditioned[cid][h].append(y)

            for name,spec in EXPECTED_SCOPE.items():
                required_bin="GE_10PCT" if spec["candidate_id"]=="H4_ROOM_PCT_GE_10PCT" else "5_10PCT"
                if b!=required_bin:continue
                if not context[as_of].get(spec["regime_id"],False):continue
                memberships[name].add((symbol,as_of))
                for h in spec["horizons"]:
                    o=(row.get("outcomes") or {}).get(str(h)) or {}
                    if o.get("status")=="MATURED":
                        returns[name][h].append(-float(o["forward_return"]))

    evidence=[]
    for name,spec in EXPECTED_SCOPE.items():
        for h in spec["horizons"]:
            s=stats(returns[name][h])
            b=stats(unconditioned[spec["candidate_id"]][h])
            evidence.append({
                "authorized_name":name,
                "candidate_id":spec["candidate_id"],
                "regime_id":spec["regime_id"],
                "concept":spec["concept"],
                "horizon_sessions":h,
                **s,
                "unconditioned_candidate_count":b["count"],
                "unconditioned_candidate_accuracy":b["accuracy"],
                "unconditioned_candidate_median":b["median"],
                "accuracy_delta_vs_unconditioned_candidate":None if s["accuracy"] is None else s["accuracy"]-b["accuracy"],
                "median_delta_vs_unconditioned_candidate":None if s["median"] is None else s["median"]-b["median"],
                "minimum_validation_count":MIN_VALIDATION_COUNT,
                "validation_pass":(
                    s["count"]>=MIN_VALIDATION_COUNT
                    and s["accuracy"] is not None and s["accuracy"]>0.5
                    and s["median"] is not None and s["median"]>0
                ),
            })

    summary={}
    for name,spec in EXPECTED_SCOPE.items():
        rows=[x for x in evidence if x["authorized_name"]==name]
        summary[name]={
            "candidate_id":spec["candidate_id"],
            "regime_id":spec["regime_id"],
            "concept":spec["concept"],
            "validation_membership_count":len(memberships[name]),
            "passed_horizons":[x["horizon_sessions"] for x in rows if x["validation_pass"]],
            "failed_horizons":[x["horizon_sessions"] for x in rows if not x["validation_pass"]],
            "all_horizons_pass":all(x["validation_pass"] for x in rows),
            "any_horizon_pass":any(x["validation_pass"] for x in rows),
        }

    report={
        "version":VERSION,
        "status":"READY",
        "advancement_gate_sha256":sha256_file(gp),
        "regime_authority_sha256":sha256_file(rp),
        "context_authority_sha256":sha256_file(cp),
        "context_csv_sha256":sha256_file(cc),
        "h4_authority_sha256":sha256_file(hp),
        "outcome_authority_sha256":EXPECTED_OUTCOME_SHA,
        "validation_window":{"start":VAL_START,"end":VAL_END},
        "minimum_validation_count":MIN_VALIDATION_COUNT,
        "authorized_scope":EXPECTED_SCOPE,
        "evidence":evidence,
        "candidate_summary":summary,
        "validation_gate_result":{
            "candidate_family_survives_validation":any(v["any_horizon_pass"] for v in summary.values()),
            "fully_surviving_candidate_count":sum(v["all_horizons_pass"] for v in summary.values()),
            "partially_surviving_candidate_count":sum(v["any_horizon_pass"] and not v["all_horizons_pass"] for v in summary.values()),
            "failed_candidate_count":sum(not v["any_horizon_pass"] for v in summary.values()),
            "final_holdout_open_authorized":False,
        },
        "scope_protection":{
            "development_context_rows_skipped":development_context_rows_skipped,
            "development_geometry_rows_skipped":development_geometry_rows_skipped,
            "development_outcome_rows_skipped":development_outcome_rows_skipped,
            "validation_context_rows_used":validation_context_rows_seen,
            "final_holdout_context_rows_seen":final_holdout_context_rows_seen,
            "final_holdout_geometry_rows_seen_and_skipped":final_holdout_geometry_rows_skipped,
            "final_holdout_outcome_rows_seen_and_skipped":final_holdout_outcome_rows_seen_and_skipped,
            "unauthorized_candidate_scoring_performed":False,
            "unauthorized_horizon_scoring_performed":False,
            "scope_expansion_performed":False,
        },
        "governance":{
            "development_scoring_performed":False,
            "validation_scoring_performed":True,
            "final_holdout_scoring_performed":False,
            "final_holdout_opened":False,
            "candidate_definitions_changed":False,
            "regime_thresholds_changed":False,
            "regime_combinations_changed":False,
            "threshold_search_or_optimization":False,
            "regime_search_or_optimization":False,
            "parameter_fitting":False,
            "classifier_training":False,
            "automatic_bearish_signal_inversion":False,
            "production_model_change_authorized":False,
            "production_authority_effect":False,
        },
        "next_step":"REVIEW_M77_19_7_4_20_VALIDATION_EVIDENCE_BEFORE_ANY_FINAL_HOLDOUT_AUTHORIZATION",
    }

    outj=Path(args.output_json);outc=Path(args.output_csv)
    if not outj.is_absolute():outj=root/outj
    if not outc.is_absolute():outc=root/outc
    atomic_json(outj,report)

    outc.parent.mkdir(parents=True,exist_ok=True)
    fields=list(evidence[0].keys())
    with outc.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(evidence)

    print("=== M77.19.7.4.20 AUTHORIZED REGIME-CONDITIONED VALIDATION-ONLY EVALUATION ===")
    print("status: READY")
    print(f"validation_window: {VAL_START} .. {VAL_END}")
    print(f"minimum_validation_count: {MIN_VALIDATION_COUNT}")
    for e in evidence:
        print(f"{e['authorized_name']}__h{e['horizon_sessions']}: "
              f"count={e['count']} accuracy={e['accuracy']} median={e['median']} "
              f"accuracy_delta={e['accuracy_delta_vs_unconditioned_candidate']} "
              f"median_delta={e['median_delta_vs_unconditioned_candidate']} "
              f"validation_pass={e['validation_pass']}")
    for name,s in summary.items():
        print(f"{name}: validation_membership_count={s['validation_membership_count']} "
              f"passed_horizons={s['passed_horizons']} failed_horizons={s['failed_horizons']} "
              f"all_horizons_pass={s['all_horizons_pass']} any_horizon_pass={s['any_horizon_pass']}")
    print("candidate_family_survives_validation:", report["validation_gate_result"]["candidate_family_survives_validation"])
    print("fully_surviving_candidate_count:", report["validation_gate_result"]["fully_surviving_candidate_count"])
    print("partially_surviving_candidate_count:", report["validation_gate_result"]["partially_surviving_candidate_count"])
    print("failed_candidate_count:", report["validation_gate_result"]["failed_candidate_count"])
    print("final_holdout_open_authorized: False")
    print("development_scoring_performed: False")
    print("final_holdout_scoring_performed: False")
    print("unauthorized_candidate_scoring_performed: False")
    print("scope_expansion_performed: False")
    print("candidate_definitions_changed: False")
    print("regime_thresholds_changed: False")
    print("production_model_change_authorized: False")
    print("next_step: REVIEW_M77_19_7_4_20_VALIDATION_EVIDENCE_BEFORE_ANY_FINAL_HOLDOUT_AUTHORIZATION")
    print(f"report: {outj}")
    print(f"csv: {outc}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
