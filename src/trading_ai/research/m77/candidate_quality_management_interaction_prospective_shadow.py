from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trading_ai.research.m77.management_geometry_prospective_shadow import (
    _atomic_json,
    _atr14_at_market_date,
    _f,
    _load_ohlc,
    _metrics,
    _nonoverlap,
    _read_json,
    _resolve,
    _simulate_executable,
)

VERSION = "M77.27.1-PROSPECTIVE-CANDIDATE-QUALITY-MANAGEMENT-INTERACTION-SHADOW-1.0"
PROTOCOL_ID = "CQMI-CANDIDATE-001"
PROSPECTIVE_NOT_BEFORE = date(2026, 8, 27)

TOP_FRACTION = 0.20
HORIZON_SESSIONS = 60
TARGET_ATR = 5.0
STOP_ATR = 3.0
ENTRY_POLICY = "NEXT_OPEN"
POPULATION = "TRADE_BUILDER_READY_LONG_AND_DRVE_PASS_AND_PROBABILITY_UP_TOP20"

DEFAULT_DRVE_AUTHORITY = "data/downside_risk_veto/current_authority.json"
DEFAULT_ROOT = "data/candidate_quality_management_interaction_shadow"
DEFAULT_LEDGER = "data/candidate_quality_management_interaction_shadow/prospective_ledger.json"
DEFAULT_SUMMARY = "data/candidate_quality_management_interaction_shadow/prospective_certification_summary.json"

FROZEN_GATES = {
    "minimum_matured_observations": 250,
    "minimum_unique_symbols": 100,
    "minimum_mean_r": 0.15,
    "minimum_profit_factor": 1.30,
    "minimum_equal_symbol_mean_r": 0.12,
    "minimum_positive_symbol_fraction": 0.65,
    "minimum_nonoverlap_mean_r": 0.12,
    "minimum_nonoverlap_profit_factor": 1.25,
    "minimum_positive_month_fraction": 0.70,
    "maximum_top10_abs_contribution_fraction": 0.25,
    "maximum_gap_stop_fraction": 0.10,
    "minimum_1pct_tail_r": -2.50,
}


class InteractionShadowError(RuntimeError):
    pass


@dataclass(frozen=True)
class InteractionShadowConfig:
    project_root: str
    authority_path: str = DEFAULT_DRVE_AUTHORITY
    shadow_root: str = DEFAULT_ROOT
    ledger_path: str = DEFAULT_LEDGER
    summary_path: str = DEFAULT_SUMMARY


def _eligible_ranked(authority: dict[str,Any]) -> tuple[list[dict[str,Any]], int]:
    rows=[]
    for symbol,rec in (authority.get("records") or {}).items():
        if rec.get("trade_builder_ready_long") is not True:
            continue
        if rec.get("veto") is True:
            continue
        p=_f(rec.get("probability_up"))
        if p is None:
            continue
        rows.append({
            "symbol":str(symbol).upper(),
            "probability_up":p,
            "drve_cross_section_rank":rec.get("cross_section_rank"),
            "drve_cross_section_percentile":_f(rec.get("cross_section_percentile")),
        })
    rows=sorted(rows,key=lambda r:(-r["probability_up"],r["symbol"]))
    n=len(rows)
    if n==0:
        return [],0
    selected=max(1,int(math.ceil(n*TOP_FRACTION)))
    for i,r in enumerate(rows,start=1):
        r["probability_up_rank"]=i
        r["probability_up_percentile"]=i/n
        r["selected_top20"]=i<=selected
    return rows,selected


def write_frozen_protocol(root:Path)->Path:
    path=root/DEFAULT_ROOT/"FROZEN_PROSPECTIVE_PROTOCOL.json"
    payload={
        "version":"M77.27.1-FROZEN-PROSPECTIVE-PROTOCOL-1.0",
        "protocol_id":PROTOCOL_ID,
        "frozen_at":datetime.now(timezone.utc).isoformat(),
        "prospective_not_before":PROSPECTIVE_NOT_BEFORE.isoformat(),
        "population":POPULATION,
        "candidate_selector":"PROBABILITY_UP",
        "top_fraction":TOP_FRACTION,
        "entry_policy":ENTRY_POLICY,
        "candidate_atr_definition":"WILDER_EWM_ATR14_POINT_IN_TIME",
        "target_atr":TARGET_ATR,
        "stop_atr":STOP_ATR,
        "horizon_sessions":HORIZON_SESSIONS,
        "stop_gap_fill":"OPEN_IF_OPEN_AT_OR_BELOW_STOP",
        "target_gap_fill":"TARGET_PRICE",
        "same_bar_target_stop":"CONSERVATIVE_STOP",
        "unresolved_by_horizon":"EXIT_AT_HORIZON_CLOSE",
        "frozen_gates":FROZEN_GATES,
        "one_immutable_snapshot_per_market_date":True,
        "historical_2018_2026_forbidden_for_tuning":True,
        "psve_candidate_001_unchanged":True,
        "mge_candidate_001_unchanged":True,
        "production_authority_effect":False,
        "production_management_effect":False,
        "automatic_retraining":False,
    }
    if path.exists():
        existing=_read_json(path)
        invariant={k:existing.get(k) for k in payload if k!="frozen_at"}
        wanted={k:payload.get(k) for k in payload if k!="frozen_at"}
        if invariant!=wanted:
            raise InteractionShadowError("Frozen CQMI protocol mismatch; refusing overwrite")
        return path
    _atomic_json(path,payload)
    return path


def record_shadow_snapshot(cfg:InteractionShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    authority_path=_resolve(root,cfg.authority_path)
    if not authority_path.exists():
        raise InteractionShadowError(f"DRVE authority missing: {authority_path}")
    authority=_read_json(authority_path)
    if authority.get("feature_parity_valid") is not True:
        raise InteractionShadowError("DRVE authority feature parity invalid")
    if authority.get("production_scope")!="TRADE_BUILDER_READY_LONG_ONLY":
        raise InteractionShadowError("Unexpected DRVE production scope")

    market_date=date.fromisoformat(str(authority["market_as_of_date"]))
    if market_date<PROSPECTIVE_NOT_BEFORE:
        return {
            "status":"SKIPPED_PRE_BOUNDARY","market_as_of_date":market_date.isoformat(),
            "prospective_not_before":PROSPECTIVE_NOT_BEFORE.isoformat(),
            "production_authority_effect":False,
        }

    shadow_root=_resolve(root,cfg.shadow_root)
    snap_path=shadow_root/"snapshots"/f"{market_date.isoformat()}.json"
    if snap_path.exists():
        existing=_read_json(snap_path)
        return {
            "status":"ALREADY_FROZEN","market_as_of_date":market_date.isoformat(),
            "stock_scanner_run_id":existing.get("stock_scanner_run_id"),
            "eligible_count":existing.get("eligible_count",0),
            "selected_count":existing.get("selected_count",0),
            "atr_ready_count":existing.get("atr_ready_count",0),
            "production_authority_effect":False,
        }

    ranked,selected_n=_eligible_ranked(authority)
    selected=[r for r in ranked if r["selected_top20"]]
    symbols={r["symbol"] for r in selected}
    history=_load_ohlc(root,symbols,market_date-timedelta(days=730),market_date)

    frozen=[];missing=[]
    for rec in selected:
        sym=rec["symbol"]
        atr=_atr14_at_market_date(history.get(sym,pd.DataFrame()),market_date)
        if atr is None:
            missing.append(sym)
            continue
        frozen.append({**rec,"candidate_atr":atr})

    payload={
        "version":VERSION,"protocol_id":PROTOCOL_ID,
        "frozen_at":datetime.now(timezone.utc).isoformat(),
        "market_as_of_date":market_date.isoformat(),
        "stock_scanner_run_id":authority.get("stock_scanner_run_id"),
        "source_authority_generated_at":authority.get("generated_at"),
        "source_model_fingerprint":authority.get("model_fingerprint"),
        "population":POPULATION,
        "candidate_selector":"PROBABILITY_UP","top_fraction":TOP_FRACTION,
        "entry_policy":ENTRY_POLICY,"target_atr":TARGET_ATR,"stop_atr":STOP_ATR,
        "horizon_sessions":HORIZON_SESSIONS,
        "eligible_count":len(ranked),"selected_count":selected_n,
        "atr_ready_count":len(frozen),"atr_missing_symbols":missing,
        "records":frozen,
        "immutable_first_snapshot_per_market_date":True,
        "psve_candidate_001_unchanged":True,"mge_candidate_001_unchanged":True,
        "production_authority_effect":False,"production_management_effect":False,
        "automatic_retraining":False,
    }
    _atomic_json(snap_path,payload)
    return {
        "status":"FROZEN","market_as_of_date":market_date.isoformat(),
        "stock_scanner_run_id":payload["stock_scanner_run_id"],
        "eligible_count":len(ranked),"selected_count":selected_n,
        "atr_ready_count":len(frozen),"atr_missing_count":len(missing),
        "snapshot_path":str(snap_path.relative_to(root)),
        "production_authority_effect":False,
    }


def _mature_one(rec:dict[str,Any],asof:date,history:pd.DataFrame)->dict[str,Any]|None:
    if history.empty:
        return None
    dates=list(history["session_date"])
    try:
        i=dates.index(asof)
    except ValueError:
        return None
    entry_idx=i+1
    terminal_idx=entry_idx+HORIZON_SESSIONS
    if terminal_idx>=len(history):
        return None
    entry=float(history.iloc[entry_idx]["open"])
    atr=float(rec["candidate_atr"])
    if not (math.isfinite(entry) and entry>0 and math.isfinite(atr) and atr>0):
        return None
    future=history.iloc[entry_idx+1:terminal_idx+1][["open","high","low","close"]]
    horizon_close=float(history.iloc[terminal_idx]["close"])
    sim=_simulate_executable(future,entry,atr,TARGET_ATR,STOP_ATR,horizon_close)
    return {
        "entry_date":history.iloc[entry_idx]["session_date"].isoformat(),
        "entry_price":entry,
        "target_price":entry+TARGET_ATR*atr,
        "stop_price":entry-STOP_ATR*atr,
        "outcome_date":history.iloc[terminal_idx]["session_date"].isoformat(),
        **sim,
    }


def update_matured_outcomes(cfg:InteractionShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    shadow_root=_resolve(root,cfg.shadow_root)
    snaps=sorted((shadow_root/"snapshots").glob("*.json")) if (shadow_root/"snapshots").exists() else []
    if not snaps:
        summary=evaluate_prospective(cfg)
        return {"status":"NO_SNAPSHOTS","matured_new":0,**summary}

    parsed=[_read_json(p) for p in snaps]
    symbols={str(r["symbol"]).upper() for s in parsed for r in (s.get("records") or [])}
    first=min(date.fromisoformat(s["market_as_of_date"]) for s in parsed)
    histories=_load_ohlc(root,symbols,first)

    ledger_path=_resolve(root,cfg.ledger_path)
    ledger=_read_json(ledger_path) if ledger_path.exists() else {
        "version":VERSION,"protocol_id":PROTOCOL_ID,"records":{},
        "production_authority_effect":False,"production_management_effect":False,
        "automatic_retraining":False,
    }
    records=ledger.setdefault("records",{})
    new_count=0
    for snap in parsed:
        asof=date.fromisoformat(snap["market_as_of_date"])
        for rec in snap.get("records") or []:
            sym=str(rec["symbol"]).upper()
            key=f"{asof.isoformat()}|{sym}"
            if key in records:
                continue
            matured=_mature_one(rec,asof,histories.get(sym,pd.DataFrame()))
            if matured is None:
                continue
            records[key]={
                "market_as_of_date":asof.isoformat(),"symbol":sym,
                "candidate_atr":rec["candidate_atr"],
                "probability_up":rec.get("probability_up"),
                "probability_up_rank":rec.get("probability_up_rank"),
                "probability_up_percentile":rec.get("probability_up_percentile"),
                "drve_cross_section_percentile":rec.get("drve_cross_section_percentile"),
                **matured,
            }
            new_count+=1
    ledger["updated_at"]=datetime.now(timezone.utc).isoformat()
    _atomic_json(ledger_path,ledger)
    summary=evaluate_prospective(cfg)
    return {"status":"COMPLETE","matured_new":new_count,**summary}


def evaluate_prospective(cfg:InteractionShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    ledger_path=_resolve(root,cfg.ledger_path)
    summary_path=_resolve(root,cfg.summary_path)
    records=(_read_json(ledger_path).get("records") or {}) if ledger_path.exists() else {}
    frame=pd.DataFrame(list(records.values()))
    if frame.empty:
        summary={
            "version":VERSION,"protocol_id":PROTOCOL_ID,"status":"ACCUMULATING",
            "matured_observations":0,"matured_symbols":0,
            "certification_verdict":"NOT_ENOUGH_PROSPECTIVE_EVIDENCE",
            "frozen_gates":FROZEN_GATES,"production_authority_effect":False,
        }
        _atomic_json(summary_path,summary)
        return summary

    frame["market_as_of_date"]=pd.to_datetime(frame["market_as_of_date"])
    frame["entry_date"]=pd.to_datetime(frame["entry_date"])
    m=_metrics(frame)
    nm=_metrics(_nonoverlap(frame))

    months=[]
    for period,g in frame.groupby(frame["market_as_of_date"].dt.to_period("M")):
        mm=_metrics(g)
        months.append({"month":str(period),"n":mm.get("n",0),"mean_r":mm.get("mean_r"),
                       "positive":bool(mm.get("mean_r",0)>0)})
    positive_month_fraction=float(np.mean([x["positive"] for x in months])) if months else np.nan

    gates={
        "minimum_matured_observations":m.get("n",0)>=FROZEN_GATES["minimum_matured_observations"],
        "minimum_unique_symbols":m.get("symbols",0)>=FROZEN_GATES["minimum_unique_symbols"],
        "minimum_mean_r":bool(np.isfinite(m.get("mean_r",np.nan)) and m["mean_r"]>=FROZEN_GATES["minimum_mean_r"]),
        "minimum_profit_factor":bool(np.isfinite(m.get("profit_factor",np.nan)) and m["profit_factor"]>=FROZEN_GATES["minimum_profit_factor"]),
        "minimum_equal_symbol_mean_r":bool(np.isfinite(m.get("equal_symbol_mean_r",np.nan)) and m["equal_symbol_mean_r"]>=FROZEN_GATES["minimum_equal_symbol_mean_r"]),
        "minimum_positive_symbol_fraction":bool(np.isfinite(m.get("positive_symbol_fraction",np.nan)) and m["positive_symbol_fraction"]>=FROZEN_GATES["minimum_positive_symbol_fraction"]),
        "minimum_nonoverlap_mean_r":bool(np.isfinite(nm.get("mean_r",np.nan)) and nm["mean_r"]>=FROZEN_GATES["minimum_nonoverlap_mean_r"]),
        "minimum_nonoverlap_profit_factor":bool(np.isfinite(nm.get("profit_factor",np.nan)) and nm["profit_factor"]>=FROZEN_GATES["minimum_nonoverlap_profit_factor"]),
        "minimum_positive_month_fraction":bool(np.isfinite(positive_month_fraction) and positive_month_fraction>=FROZEN_GATES["minimum_positive_month_fraction"]),
        "maximum_top10_abs_contribution_fraction":bool(np.isfinite(m.get("top10_abs_contribution_fraction",np.nan)) and m["top10_abs_contribution_fraction"]<=FROZEN_GATES["maximum_top10_abs_contribution_fraction"]),
        "maximum_gap_stop_fraction":bool(np.isfinite(m.get("gap_stop_fraction",np.nan)) and m["gap_stop_fraction"]<=FROZEN_GATES["maximum_gap_stop_fraction"]),
        "minimum_1pct_tail_r":bool(np.isfinite(m.get("tail_1pct_r",np.nan)) and m["tail_1pct_r"]>=FROZEN_GATES["minimum_1pct_tail_r"]),
    }
    enough=gates["minimum_matured_observations"] and gates["minimum_unique_symbols"]
    verdict="PASS" if enough and all(gates.values()) else ("FAIL" if enough else "NOT_ENOUGH_PROSPECTIVE_EVIDENCE")
    summary={
        "version":VERSION,"protocol_id":PROTOCOL_ID,"status":"COMPLETE",
        "population":POPULATION,"candidate_selector":"PROBABILITY_UP","top_fraction":TOP_FRACTION,
        "entry_policy":ENTRY_POLICY,"target_atr":TARGET_ATR,"stop_atr":STOP_ATR,"horizon_sessions":HORIZON_SESSIONS,
        "matured_observations":m.get("n",0),"matured_symbols":m.get("symbols",0),
        "metrics":m,"nonoverlap_metrics":nm,
        "positive_month_fraction":positive_month_fraction,"month_evidence":months,
        "frozen_gates":FROZEN_GATES,"gate_results":gates,
        "certification_verdict":verdict,
        "psve_candidate_001_unchanged":True,"mge_candidate_001_unchanged":True,
        "historical_retuning_performed":False,"automatic_retraining":False,
        "production_authority_effect":False,"production_management_effect":False,
    }
    _atomic_json(summary_path,summary)
    return summary


def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.27.1 prospective candidate-quality x management interaction shadow")
    p.add_argument("--project-root",required=True)
    p.add_argument("--action",choices=("freeze","record","update","evaluate"),default="record")
    return p


def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    root=Path(a.project_root).expanduser().resolve()
    cfg=InteractionShadowConfig(project_root=str(root))
    path=write_frozen_protocol(root)
    if a.action=="freeze":
        result={"status":"FROZEN","protocol_path":str(path.relative_to(root))}
    elif a.action=="record":
        result=record_shadow_snapshot(cfg)
    elif a.action=="update":
        result=update_matured_outcomes(cfg)
    else:
        result=evaluate_prospective(cfg)
    print(json.dumps(result,indent=2,sort_keys=True,default=str))
    return 0
