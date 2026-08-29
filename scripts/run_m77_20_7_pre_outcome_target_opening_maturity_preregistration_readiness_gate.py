#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json
from datetime import date
from pathlib import Path
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

VERSION="M77.20.7-PRE-OUTCOME-TARGET-OPENING-MATURITY-PREREGISTRATION-READINESS-GATE-1.0"
HORIZONS=(5,10,20)
MIN_ROWS=10000
class GateError(RuntimeError):pass

def R(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def H(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--cycle2-json",default="reports/m77_20_0_prospective_edge_cycle2_preregistration_consumed_holdout_lock_authority.json")
    ap.add_argument("--design-gate-json",default="reports/m77_20_2_external_historical_pit_sector_source_decision_prospective_only_research_design_gate.json")
    ap.add_argument("--capture-authority-json",default="reports/m77_20_6_prospective_daily_capture_orchestration_pre_outcome_accumulation_authority.json")
    ap.add_argument("--accumulation-manifest",default="research_data/m77_20_6/pre_outcome_accumulation/manifest.json")
    ap.add_argument("--market-session-symbol",default="SPY")
    ap.add_argument("--output-json",default="reports/m77_20_7_pre_outcome_target_opening_maturity_preregistration_readiness_gate.json")
    ap.add_argument("--output-csv",default="reports/m77_20_7_horizon_maturity_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    c0p,d2p,c6p,mp=[R(root,x) for x in (a.cycle2_json,a.design_gate_json,a.capture_authority_json,a.accumulation_manifest)]
    for p in (c0p,d2p,c6p,mp):
        if not p.exists():raise GateError(f"required authority/source missing: {p}")
    c0,d2,c6,m=J(c0p),J(d2p),J(c6p),J(mp)

    if c0.get("status")!="READY":raise GateError("M77.20.0 invalid")
    if d2.get("status")!="READY" or (d2.get("decision") or {}).get("prospective_only_route_selected") is not True:
        raise GateError("M77.20.2 prospective-only design invalid")
    if c6.get("status")!="READY" or c6.get("pre_outcome_accumulation_only") is not True:
        raise GateError("M77.20.6 capture authority invalid")
    # Bind governance flags to each upstream authority's certified schema.
    # M77.20.0 and M77.20.2 publish production_authority_effect under
    # execution_state; M77.20.6 publishes it at the report root.
    c0_exec=c0.get("execution_state")
    if not isinstance(c0_exec,dict):
        raise GateError("20.0: execution_state object missing")
    if c0_exec.get("production_authority_effect") is not False:
        raise GateError("20.0: execution_state.production_authority_effect changed")

    d2_exec=d2.get("execution_state")
    if not isinstance(d2_exec,dict):
        raise GateError("20.2: execution_state object missing")
    if d2_exec.get("production_authority_effect") is not False:
        raise GateError("20.2: execution_state.production_authority_effect changed")

    if c6.get("production_authority_effect") is not False:
        raise GateError("20.6: production_authority_effect changed")
    if c6.get("target_materialization_authorized") is not False or c6.get("prospective_outcomes_opened") is not False:
        raise GateError("M77.20.6 outcome boundary violated")
    if c6.get("prospective_scoring_authorized") is not False or c6.get("prospective_scoring_performed") is not False:
        raise GateError("M77.20.6 scoring boundary violated")

    prereg=(c0.get("incremental_value_test_preregistration") or {})
    adv=prereg.get("prospective_advancement_rule") or {}
    if int(adv.get("minimum_matured_binary_rows_per_horizon"))!=MIN_ROWS:
        raise GateError("preregistered minimum matured binary rows changed")
    if prereg.get("horizons")!=[5,10,20]:
        raise GateError("preregistered horizons changed")
    ev=d2.get("evaluation_contract") or {}
    if int(ev.get("minimum_matured_binary_rows_per_horizon"))!=MIN_ROWS:
        raise GateError("M77.20.2 minimum matured rows changed")

    obs=m.get("observations") or []
    sessions=[str(x["effective_observation_session"]) for x in obs]
    if len(sessions)!=len(set(sessions)):raise GateError("accumulation manifest contains duplicate effective sessions")
    if sessions!=sorted(sessions):raise GateError("accumulation manifest effective sessions are not ordered")
    if any(int(x.get("paired_observation_eligible_count",0))<0 for x in obs):raise GateError("negative paired count")

    first=min(sessions) if sessions else None
    latest=max(sessions) if sessions else None
    if latest is None:
        market_sessions=[]
    else:
        with SessionLocal() as s:
            market_sessions=[str(x[0])[:10] for x in s.execute(text("""
                SELECT DISTINCT date
                FROM price_history
                WHERE UPPER(symbol)=UPPER(:symbol)
                  AND date >= :start_date
                  AND date <= :end_date
                ORDER BY date
            """),{"symbol":a.market_session_symbol,
                   "start_date":date.fromisoformat(first),
                   "end_date":date.today()}).all()]
    market_sessions=sorted(set(market_sessions))
    index={d:i for i,d in enumerate(market_sessions)}
    latest_market_session=market_sessions[-1] if market_sessions else None
    latest_index=None if latest_market_session is None else index[latest_market_session]

    horizon_rows=[]
    all_ready=True
    for h in HORIZONS:
        potential=0;matured_capture_sessions=0;not_yet=0;unresolvable=0
        first_matured=None;last_matured=None
        for x in obs:
            d=str(x["effective_observation_session"])
            i=index.get(d)
            if i is None or latest_index is None:
                unresolvable+=1;continue
            if latest_index-i>=h:
                n=int(x["paired_observation_eligible_count"]);potential+=n;matured_capture_sessions+=1
                first_matured=d if first_matured is None else min(first_matured,d)
                last_matured=d if last_matured is None else max(last_matured,d)
            else:not_yet+=1
        ready=potential>=MIN_ROWS
        all_ready=all_ready and ready
        horizon_rows.append({
          "horizon":h,"potentially_matured_paired_rows":potential,
          "minimum_required_rows":MIN_ROWS,"pre_outcome_opening_row_floor_met":ready,
          "matured_capture_session_count":matured_capture_sessions,
          "not_yet_matured_capture_session_count":not_yet,
          "unresolvable_capture_session_count":unresolvable,
          "first_matured_observation_session":first_matured,
          "last_matured_observation_session":last_matured})

    # This gate is allowed to authorize target materialization only after all
    # horizon row floors are met. It never authorizes scoring directly.
    target_open=bool(all_ready and len(horizon_rows)==3 and all(x["unresolvable_capture_session_count"]==0 for x in horizon_rows))
    status="READY_TARGET_OPENING_AUTHORIZED" if target_open else "READY_ACCUMULATING_PRE_OUTCOME"

    report={
      "version":VERSION,"status":status,
      "upstream_sha256":{"m77_20_0":H(c0p),"m77_20_2":H(d2p),"m77_20_6":H(c6p),"accumulation_manifest":H(mp)},
      "market_session_calendar_source":"POSTGRESQL_PRICE_HISTORY_DATE_ONLY",
      "market_session_symbol":a.market_session_symbol,
      "price_values_read":False,
      "returns_read":False,
      "target_labels_read":False,
      "outcomes_read":False,
      "first_accumulated_effective_session":first,
      "latest_accumulated_effective_session":latest,
      "latest_market_session_seen":latest_market_session,
      "statistical_effective_session_count":len(obs),
      "cumulative_paired_observation_rows":sum(int(x.get("paired_observation_eligible_count",0)) for x in obs),
      "horizons":horizon_rows,
      "pre_outcome_target_opening_rule":{
        "all_horizons_required":True,
        "minimum_potentially_matured_paired_rows_per_horizon":MIN_ROWS,
        "horizon_sessions":[5,10,20],
        "rule_frozen_before_any_target_opening":True,
      },
      "post_target_binary_eligibility_rule":{
        "minimum_actual_binary_UP_DOWN_rows_per_horizon":MIN_ROWS,
        "ZERO_rows_excluded_from_binary_scoring":True,
        "missing_or_unmatured_targets_excluded":True,
        "scoring_remains_blocked_if_any_horizon_below_floor":True,
      },
      "pre_outcome_target_opening_ready":target_open,
      "target_materialization_authorized":target_open,
      "prospective_outcomes_opened":False,
      "prospective_scoring_authorized":False,
      "prospective_scoring_performed":False,
      "retuning_authorized":False,
      "threshold_search_authorized":False,
      "feature_selection_search_authorized":False,
      "hyperparameter_search_authorized":False,
      "production_authority_effect":False,
      "next_step":(
          "BUILD_M77_20_8_PROSPECTIVE_TARGET_MATERIALIZATION_AUTHORITY"
          if target_open else
          "CONTINUE_DAILY_M77_20_6_CAPTURE_AND_RERUN_M77_20_7_READINESS_GATE"
      ),
    }
    oj,oc=R(root,a.output_json),R(root,a.output_csv);oj.parent.mkdir(parents=True,exist_ok=True)
    oj.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    fields=["horizon","potentially_matured_paired_rows","minimum_required_rows","pre_outcome_opening_row_floor_met",
            "matured_capture_session_count","not_yet_matured_capture_session_count","unresolvable_capture_session_count",
            "first_matured_observation_session","last_matured_observation_session"]
    with oc.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(horizon_rows)

    print("=== M77.20.7 PRE-OUTCOME TARGET-OPENING MATURITY PREREGISTRATION & READINESS GATE ===")
    print("status:",status)
    print("market_session_calendar_source: POSTGRESQL_PRICE_HISTORY_DATE_ONLY")
    print("price_values_read: False")
    print("returns_read: False")
    print("target_labels_read: False")
    print("outcomes_read: False")
    print("statistical_effective_session_count:",len(obs))
    print("cumulative_paired_observation_rows:",report["cumulative_paired_observation_rows"])
    for x in horizon_rows:
        print(f"horizon_{x['horizon']}: potentially_matured={x['potentially_matured_paired_rows']} "
              f"minimum={MIN_ROWS} ready={x['pre_outcome_opening_row_floor_met']} "
              f"matured_sessions={x['matured_capture_session_count']}")
    print("pre_outcome_target_opening_ready:",target_open)
    print("target_materialization_authorized:",target_open)
    print("prospective_outcomes_opened: False")
    print("prospective_scoring_authorized: False")
    print("prospective_scoring_performed: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",oj);print("csv:",oc)

if __name__=="__main__":main()
