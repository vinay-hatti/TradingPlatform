#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median

VERSION = "CYCLICAL-SEASONALITY-FROZEN-CANDIDATE-TARGETED-ROBUSTNESS-1.0"

FROZEN = {
    "candidate_id": "STATE_PERSISTENCE::category_age_bucket::AGE_2_3::STRONG_BULLISH::20",
    "factor_family": "STATE_PERSISTENCE",
    "factor": "category_age_bucket",
    "state": "AGE_2_3",
    "direction": "STRONG_BULLISH",
    "horizon": 20,
}

STRICT = {
    "min_full_years": 2,
    "min_matched_n_each_full_year": 100,
    "min_coverage_pct_each_full_year": 80.0,
    "min_matched_excess_pct_each_full_year": 0.25,
    "max_fdr_q_each_full_year": 0.10,
    "min_symbols": 300,
    "max_top_10_symbol_share_pct": 15.0,
}

DATE_KEYS = ("as_of","date","session_date","observation_date","source_as_of_date","timestamp")
SYMBOL_KEYS = ("symbol","ticker")
VALUE_KEYS = (
    "matched_excess_pct","excess_return_pct","excess_pct","thesis_excess_pct",
    "thesis_return_pct","return_pct","forward_return_pct"
)

def _load(path: Path):
    return json.loads(path.read_text())

def _sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _candidate(audit):
    xs = [x for x in audit.get("candidates",[]) if x.get("candidate_id")==FROZEN["candidate_id"]]
    if len(xs) != 1:
        raise SystemExit(f"FAIL_CLOSED: expected exactly one frozen candidate, found {len(xs)}")
    return xs[0]

def _as_date(v):
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if not isinstance(v, str):
        return None
    s=v[:10]
    try:
        return date.fromisoformat(s)
    except Exception:
        return None

def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        x=float(v)
    except Exception:
        return None
    return x if math.isfinite(x) else None

def _matches_identity(d):
    cid=d.get("candidate_id")
    if cid == FROZEN["candidate_id"]:
        return True
    checks=(
        d.get("factor_family")==FROZEN["factor_family"],
        d.get("factor")==FROZEN["factor"],
        d.get("state")==FROZEN["state"],
        d.get("direction")==FROZEN["direction"],
        d.get("horizon")==FROZEN["horizon"] or d.get("horizon_sessions")==FROZEN["horizon"],
    )
    return all(checks)

def _walk(obj, inherited_match=False):
    if isinstance(obj, dict):
        here = inherited_match or _matches_identity(obj)
        yield obj, here
        for v in obj.values():
            yield from _walk(v, here)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, inherited_match)

def _extract_observations(predecessor):
    rows=[]
    seen=set()
    for d, matched in _walk(predecessor):
        if not matched:
            continue
        sym=next((d.get(k) for k in SYMBOL_KEYS if d.get(k)),None)
        dt=next((_as_date(d.get(k)) for k in DATE_KEYS if _as_date(d.get(k))),None)
        val=None
        val_key=None
        for k in VALUE_KEYS:
            x=_num(d.get(k))
            if x is not None:
                val=x;val_key=k;break
        if not sym or not dt or val is None:
            continue
        key=(str(sym),dt.isoformat(),val_key,round(val,10))
        if key in seen:
            continue
        seen.add(key)
        rows.append({"symbol":str(sym),"date":dt,"value_pct":val,"source_value_key":val_key})
    return rows

def _quarter(d):
    return f"{d.year}-Q{((d.month-1)//3)+1}"

def _bootstrap_ci(values, seed=7701, reps=4000):
    if len(values)<2:
        return [None,None]
    rnd=random.Random(seed)
    n=len(values)
    sims=[]
    for _ in range(reps):
        sims.append(mean(values[rnd.randrange(n)] for _ in range(n)))
    sims.sort()
    lo=sims[int(0.025*(reps-1))]
    hi=sims[int(0.975*(reps-1))]
    return [lo,hi]

def _cluster_groups(symbols, buckets=10):
    g=defaultdict(list)
    for s in sorted(set(symbols)):
        h=int(hashlib.sha256(s.encode()).hexdigest()[:8],16)%buckets
        g[h].append(s)
    return g

def _obs_robustness(rows):
    if not rows:
        return {
            "available": False,
            "reason": "PREDECESSOR_ARTIFACT_DOES_NOT_EXPOSE_OBSERVATION_LEVEL_VECTOR_FOR_FROZEN_CANDIDATE",
            "certification_effect": False,
        }

    by_year=defaultdict(list)
    by_quarter=defaultdict(list)
    by_symbol=defaultdict(list)
    for r in rows:
        by_year[r["date"].year].append(r["value_pct"])
        by_quarter[_quarter(r["date"])].append(r["value_pct"])
        by_symbol[r["symbol"]].append(r["value_pct"])

    full_years={str(y): {"n":len(v),"mean_pct":mean(v),"median_pct":median(v)}
                for y,v in sorted(by_year.items()) if y in (2024,2025)}
    quarters={q: {"n":len(v),"mean_pct":mean(v),"median_pct":median(v)}
              for q,v in sorted(by_quarter.items()) if q.startswith("2024-") or q.startswith("2025-")}

    vals=[r["value_pct"] for r in rows if r["date"].year in (2024,2025)]
    symbols=[r["symbol"] for r in rows if r["date"].year in (2024,2025)]
    groups=_cluster_groups(symbols,10)
    loo=[]
    all_rows=[r for r in rows if r["date"].year in (2024,2025)]
    for gid, members in sorted(groups.items()):
        ms=set(members)
        rem=[r["value_pct"] for r in all_rows if r["symbol"] not in ms]
        loo.append({"cluster":gid,"removed_symbols":len(ms),"remaining_n":len(rem),
                    "remaining_mean_pct":mean(rem) if rem else None})

    positive_quarters=sum(1 for x in quarters.values() if x["mean_pct"]>0)
    qualifying_quarters=sum(1 for x in quarters.values() if x["n"]>=50)
    positive_qualifying=sum(1 for x in quarters.values() if x["n"]>=50 and x["mean_pct"]>0)
    loo_positive=sum(1 for x in loo if x["remaining_mean_pct"] is not None and x["remaining_mean_pct"]>0)

    return {
        "available": True,
        "rows": len(all_rows),
        "symbols": len(set(symbols)),
        "source_value_keys": dict(Counter(r["source_value_key"] for r in rows)),
        "full_year": full_years,
        "quarter": quarters,
        "quarter_stability": {
            "positive_quarters": positive_quarters,
            "qualifying_quarters_n_ge_50": qualifying_quarters,
            "positive_qualifying_quarters": positive_qualifying,
            "positive_qualifying_fraction": (
                positive_qualifying/qualifying_quarters if qualifying_quarters else None
            ),
        },
        "bootstrap_mean_pct_95_ci": _bootstrap_ci(vals),
        "leave_symbol_hash_cluster_out": loo,
        "leave_symbol_hash_cluster_out_positive": loo_positive,
        "leave_symbol_hash_cluster_out_total": len(loo),
        "certification_effect": False,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit",default="reports/cyclical_seasonality/cyclical_seasonality_candidate_refinement_stability_audit.json")
    ap.add_argument("--predecessor",default="reports/cyclical_seasonality/cyclical_seasonality_fold_native_shadow_certification.json")
    ap.add_argument("--output",default="reports/cyclical_seasonality/cyclical_seasonality_frozen_candidate_targeted_robustness.json")
    a=ap.parse_args()

    audit_p=Path(a.audit); pred_p=Path(a.predecessor); out_p=Path(a.output)
    if not audit_p.exists(): raise SystemExit(f"missing audit artifact: {audit_p}")
    if not pred_p.exists(): raise SystemExit(f"missing predecessor artifact: {pred_p}")

    audit=_load(audit_p); predecessor=_load(pred_p)
    if audit.get("version")!="CYCLICAL-SEASONALITY-CANDIDATE-REFINEMENT-STABILITY-AUDIT-1.0":
        raise SystemExit("FAIL_CLOSED: unexpected refinement audit version")
    gov=audit.get("governance",{})
    for k in ("production_authority_effect","production_model_mutation","production_threshold_change",
              "production_weight_change","production_decision_change","automatic_shadow_activation",
              "automatic_champion_promotion","certification_thresholds_relaxed"):
        if gov.get(k) is not False:
            raise SystemExit(f"FAIL_CLOSED: predecessor governance violation: {k}")

    cand=_candidate(audit)
    if cand.get("classification")!="NEAR_CERTIFICATION_FDR_ONLY":
        raise SystemExit("FAIL_CLOSED: frozen candidate is no longer the unique near-certification candidate")

    fy=cand["full_year"]
    years=(2024,2025)
    metrics=[]
    for i,y in enumerate(years):
        metrics.append({
            "year":y,
            "matched_excess_pct":fy["matched_excess_pct"][i],
            "fdr_q":fy["fdr_q"][i],
            "thesis_return_pct":fy["thesis_return_pct"][i],
            "coverage_pct":fy["coverage_pct"][i],
            "matched_n":fy["matched_n"][i],
        })

    strict_checks={
        "both_years_n_ge_100": all(x["matched_n"]>=STRICT["min_matched_n_each_full_year"] for x in metrics),
        "both_years_coverage_ge_80": all(x["coverage_pct"]>=STRICT["min_coverage_pct_each_full_year"] for x in metrics),
        "both_years_excess_ge_0_25": all(x["matched_excess_pct"]>=STRICT["min_matched_excess_pct_each_full_year"] for x in metrics),
        "both_years_thesis_positive": all(x["thesis_return_pct"]>0 for x in metrics),
        "both_years_q_le_0_10": all(x["fdr_q"]<=STRICT["max_fdr_q_each_full_year"] for x in metrics),
        "symbol_breadth_ge_300": cand["symbol_membership_concentration"]["symbols"]>=STRICT["min_symbols"],
        "top10_symbol_share_le_15pct": cand["symbol_membership_concentration"]["top_10_symbol_share_pct"]<=STRICT["max_top_10_symbol_share_pct"],
    }

    observation_rows=_extract_observations(predecessor)
    obs=_obs_robustness(observation_rows)

    # Historical certification gate is intentionally immutable. Robustness diagnostics
    # can support or reject further research but cannot retroactively certify a q>0.10 fold.
    strict_certified=all(strict_checks.values())
    if strict_certified:
        disposition="STRICT_HISTORICAL_GATE_SATISFIED_REQUIRES_SEPARATE_SHADOW_APPROVAL"
    elif all(v for k,v in strict_checks.items() if k!="both_years_q_le_0_10") and not strict_checks["both_years_q_le_0_10"]:
        disposition="HISTORICAL_ROBUSTNESS_CANDIDATE_FDR_ONLY_FAILURE_RETAIN_RESEARCH_ONLY"
    else:
        disposition="REJECT_TARGETED_CANDIDATE"

    out={
        "version":VERSION,
        "status":"READY",
        "governance":{
            "research_only":True,
            "read_only_artifact_analysis":True,
            "database_writes":False,
            "database_migrations":False,
            "production_authority_effect":False,
            "production_model_mutation":False,
            "production_threshold_change":False,
            "production_weight_change":False,
            "production_decision_change":False,
            "automatic_shadow_activation":False,
            "automatic_champion_promotion":False,
            "certification_thresholds_relaxed":False,
            "neighbor_candidate_search_prohibited":True,
        },
        "lineage":{
            "audit":str(audit_p),
            "audit_sha256":_sha(audit_p),
            "predecessor":str(pred_p),
            "predecessor_sha256":_sha(pred_p),
        },
        "frozen_candidate":FROZEN,
        "strict_existing_gate":STRICT,
        "full_year_metrics":metrics,
        "strict_checks":strict_checks,
        "strict_historical_certified":strict_certified,
        "observation_level_robustness":obs,
        "disposition":disposition,
        "next_action":(
            "DO_NOT_ACTIVATE_SHADOW_OR_PRODUCTION; accumulate genuinely new forward evidence "
            "unless strict historical q<=0.10 is satisfied in every required full-year fold."
            if not strict_certified else
            "SEPARATE_GOVERNED_RESEARCH_SHADOW_APPROVAL_REQUIRED"
        ),
    }
    out_p.parent.mkdir(parents=True,exist_ok=True)
    out_p.write_text(json.dumps(out,indent=2,default=str)+"\n")
    print(json.dumps({
        "status":"READY",
        "version":VERSION,
        "output":str(out_p),
        "candidate_id":FROZEN["candidate_id"],
        "strict_historical_certified":strict_certified,
        "observation_vector_available":obs.get("available",False),
        "disposition":disposition,
        "production_authority_effect":False,
        "automatic_shadow_activation":False,
    },indent=2))

if __name__=="__main__":
    main()
