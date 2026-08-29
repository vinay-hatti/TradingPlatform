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

from trading_ai.research.m77.executable_management_geometry_recalibration import _simulate_executable

VERSION = "M77.26.2-PROSPECTIVE-EXECUTABLE-MANAGEMENT-GEOMETRY-SHADOW-1.0"
PROTOCOL_ID = "MGE-CANDIDATE-001"
PROSPECTIVE_NOT_BEFORE = date(2026, 8, 27)

HORIZON_SESSIONS = 60
TARGET_ATR = 5.0
STOP_ATR = 3.0
ENTRY_POLICY = "NEXT_OPEN"
POPULATION = "TRADE_BUILDER_READY_LONG_AND_DRVE_PASS"

DEFAULT_DRVE_AUTHORITY = "data/downside_risk_veto/current_authority.json"
DEFAULT_ROOT = "data/management_geometry_shadow"
DEFAULT_LEDGER = "data/management_geometry_shadow/prospective_ledger.json"
DEFAULT_SUMMARY = "data/management_geometry_shadow/prospective_certification_summary.json"

FROZEN_GATES = {
    "minimum_matured_observations": 300,
    "minimum_unique_symbols": 100,
    "minimum_mean_r": 0.10,
    "minimum_profit_factor": 1.20,
    "minimum_equal_symbol_mean_r": 0.075,
    "minimum_positive_symbol_fraction": 0.60,
    "minimum_nonoverlap_mean_r": 0.075,
    "minimum_nonoverlap_profit_factor": 1.15,
    "minimum_positive_month_fraction": 0.70,
    "maximum_top10_abs_contribution_fraction": 0.25,
    "maximum_gap_stop_fraction": 0.10,
    "minimum_1pct_tail_r": -2.50,
}


class ManagementShadowError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManagementShadowConfig:
    project_root: str
    authority_path: str = DEFAULT_DRVE_AUTHORITY
    shadow_root: str = DEFAULT_ROOT
    ledger_path: str = DEFAULT_LEDGER
    summary_path: str = DEFAULT_SUMMARY


def _resolve(root: Path, raw: str) -> Path:
    p=Path(raw).expanduser()
    return p if p.is_absolute() else root/p


def _read_json(path: Path) -> dict[str,Any]:
    return json.loads(path.read_text())


def _atomic_json(path: Path,payload:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True,default=str))
    os.replace(tmp,path)


def _f(v:Any)->float|None:
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _price_history_schema(session)->dict[str,str]:
    from sqlalchemy import text
    cols=session.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name='price_history'
    """)).scalars().all()
    colset={str(c) for c in cols}
    date_col=next((c for c in ("session_date","date","market_date","timestamp") if c in colset),None)
    if date_col is None:
        raise ManagementShadowError("price_history has no supported session date column")
    required={"symbol","open","high","low","close"}
    missing=required-colset
    if missing:
        raise ManagementShadowError(f"price_history missing required columns: {sorted(missing)}")
    return {"date":date_col}


def _load_ohlc(
    root:Path,
    symbols:set[str],
    start_date:date,
    end_date:date|None=None,
)->dict[str,pd.DataFrame]:
    if not symbols:
        return {}
    from sqlalchemy import text
    from trading_ai.database.session import SessionLocal
    session=SessionLocal()
    try:
        schema=_price_history_schema(session)
        dc=schema["date"]
        end_clause=f"AND {dc} <= :end_date" if end_date is not None else ""
        stmt=text(f"""
            SELECT symbol, {dc} AS session_date, open, high, low, close
            FROM price_history
            WHERE symbol = ANY(:symbols)
              AND {dc} >= :start_date
              {end_clause}
            ORDER BY symbol, {dc}
        """)
        params={"symbols":sorted(symbols),"start_date":start_date}
        if end_date is not None:params["end_date"]=end_date
        rows=session.execute(stmt,params).mappings().all()
    finally:
        session.close()

    grouped:dict[str,list[dict[str,Any]]]={}
    for r in rows:
        sym=str(r["symbol"]).upper()
        d=r["session_date"]
        if isinstance(d,datetime):d=d.date()
        elif not isinstance(d,date):d=date.fromisoformat(str(d)[:10])
        vals={k:_f(r[k]) for k in ("open","high","low","close")}
        if any(vals[k] is None for k in vals):
            continue
        grouped.setdefault(sym,[]).append({"session_date":d,**vals})

    out={}
    for sym,items in grouped.items():
        df=pd.DataFrame(items).sort_values("session_date").drop_duplicates("session_date",keep="last").reset_index(drop=True)
        out[sym]=df
    return out


def _atr14_at_market_date(df:pd.DataFrame,market_date:date)->float|None:
    if df.empty:return None
    x=df[df["session_date"]<=market_date].copy()
    if x.empty or x.iloc[-1]["session_date"]!=market_date:
        return None
    prev=x["close"].shift(1)
    tr=pd.concat([
        (x["high"]-x["low"]).abs(),
        (x["high"]-prev).abs(),
        (x["low"]-prev).abs(),
    ],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean().iloc[-1]
    return float(atr) if math.isfinite(float(atr)) and float(atr)>0 else None


def _eligible_records(authority:dict[str,Any])->list[dict[str,Any]]:
    rows=[]
    for symbol,rec in (authority.get("records") or {}).items():
        if rec.get("trade_builder_ready_long") is not True:continue
        if rec.get("veto") is True:continue
        rows.append({
            "symbol":str(symbol).upper(),
            "probability_up":_f(rec.get("probability_up")),
            "drve_cross_section_rank":rec.get("cross_section_rank"),
            "drve_cross_section_percentile":_f(rec.get("cross_section_percentile")),
        })
    return sorted(rows,key=lambda r:r["symbol"])


def write_frozen_protocol(root:Path)->Path:
    path=root/DEFAULT_ROOT/"FROZEN_PROSPECTIVE_PROTOCOL.json"
    payload={
        "version":"M77.26.2-FROZEN-PROSPECTIVE-PROTOCOL-1.0",
        "protocol_id":PROTOCOL_ID,
        "frozen_at":datetime.now(timezone.utc).isoformat(),
        "prospective_not_before":PROSPECTIVE_NOT_BEFORE.isoformat(),
        "population":POPULATION,
        "entry_policy":ENTRY_POLICY,
        "target_atr":TARGET_ATR,
        "stop_atr":STOP_ATR,
        "horizon_sessions":HORIZON_SESSIONS,
        "candidate_atr_definition":"WILDER_EWM_ATR14_POINT_IN_TIME",
        "stop_gap_fill":"OPEN_IF_OPEN_AT_OR_BELOW_STOP",
        "target_gap_fill":"TARGET_PRICE",
        "same_bar_target_stop":"CONSERVATIVE_STOP",
        "unresolved_by_horizon":"EXIT_AT_HORIZON_CLOSE",
        "frozen_gates":FROZEN_GATES,
        "one_immutable_snapshot_per_market_date":True,
        "historical_2018_2026_forbidden_for_tuning":True,
        "production_authority_effect":False,
        "production_management_effect":False,
        "automatic_retraining":False,
    }
    if path.exists():
        existing=_read_json(path)
        invariant={k:existing.get(k) for k in payload if k!="frozen_at"}
        wanted={k:payload.get(k) for k in payload if k!="frozen_at"}
        if invariant!=wanted:
            raise ManagementShadowError("Frozen MGE protocol mismatch; refusing overwrite")
        return path
    _atomic_json(path,payload)
    return path


def record_shadow_snapshot(cfg:ManagementShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    authority_path=_resolve(root,cfg.authority_path)
    if not authority_path.exists():
        raise ManagementShadowError(f"DRVE authority missing: {authority_path}")
    authority=_read_json(authority_path)
    if authority.get("feature_parity_valid") is not True:
        raise ManagementShadowError("DRVE authority feature parity invalid")
    if authority.get("production_scope")!="TRADE_BUILDER_READY_LONG_ONLY":
        raise ManagementShadowError("Unexpected DRVE production scope")

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
            "candidate_count":existing.get("candidate_count",0),
            "atr_ready_count":existing.get("atr_ready_count",0),
            "production_authority_effect":False,
        }

    eligible=_eligible_records(authority)
    symbols={r["symbol"] for r in eligible}
    # 730 calendar days gives ~500 sessions. This makes the Wilder EWM seed
    # effectively converged while keeping the production shadow query bounded.
    history=_load_ohlc(root,symbols,market_date-timedelta(days=730),market_date)
    frozen=[];missing=[]
    for rec in eligible:
        sym=rec["symbol"];atr=_atr14_at_market_date(history.get(sym,pd.DataFrame()),market_date)
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
        "population":POPULATION,"entry_policy":ENTRY_POLICY,
        "target_atr":TARGET_ATR,"stop_atr":STOP_ATR,"horizon_sessions":HORIZON_SESSIONS,
        "candidate_count":len(eligible),"atr_ready_count":len(frozen),
        "atr_missing_symbols":missing,"records":frozen,
        "immutable_first_snapshot_per_market_date":True,
        "production_authority_effect":False,"production_management_effect":False,
        "automatic_retraining":False,
    }
    _atomic_json(snap_path,payload)
    return {
        "status":"FROZEN","market_as_of_date":market_date.isoformat(),
        "stock_scanner_run_id":payload["stock_scanner_run_id"],
        "candidate_count":len(eligible),"atr_ready_count":len(frozen),
        "atr_missing_count":len(missing),
        "snapshot_path":str(snap_path.relative_to(root)),
        "production_authority_effect":False,
    }


def _mature_one(rec:dict[str,Any],asof:date,history:pd.DataFrame)->dict[str,Any]|None:
    if history.empty:return None
    dates=list(history["session_date"])
    try:i=dates.index(asof)
    except ValueError:return None
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


def update_matured_outcomes(cfg:ManagementShadowConfig)->dict[str,Any]:
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
            if key in records:continue
            matured=_mature_one(rec,asof,histories.get(sym,pd.DataFrame()))
            if matured is None:continue
            records[key]={
                "market_as_of_date":asof.isoformat(),"symbol":sym,
                "candidate_atr":rec["candidate_atr"],
                "probability_up":rec.get("probability_up"),
                "drve_cross_section_percentile":rec.get("drve_cross_section_percentile"),
                **matured,
            }
            new_count+=1

    ledger["updated_at"]=datetime.now(timezone.utc).isoformat()
    _atomic_json(ledger_path,ledger)
    summary=evaluate_prospective(cfg)
    return {"status":"COMPLETE","matured_new":new_count,**summary}


def _metrics(frame:pd.DataFrame)->dict[str,Any]:
    if frame.empty:return {"n":0}
    r=pd.to_numeric(frame["r_multiple"],errors="coerce").dropna()
    if r.empty:return {"n":0}
    x=frame.loc[r.index]
    gross_profit=float(r[r>0].sum());gross_loss=float(-r[r<0].sum())
    sym=x.assign(_r=r).groupby("symbol")["_r"].mean()
    contrib=x.assign(_r=r).groupby("symbol")["_r"].sum().abs().sort_values(ascending=False)
    denom=float(contrib.sum())
    gap=x["exit_type"].eq("STOP_GAP")
    return {
        "n":int(len(r)),"symbols":int(x["symbol"].nunique()),
        "mean_r":float(r.mean()),"median_r":float(r.median()),
        "win_rate":float((r>0).mean()),
        "profit_factor":float(gross_profit/gross_loss) if gross_loss>0 else np.inf,
        "target_exit_fraction":float(x["exit_type"].isin(["TARGET","TARGET_GAP"]).mean()),
        "stop_exit_fraction":float(x["exit_type"].isin(["STOP","STOP_GAP","AMBIGUOUS_STOP_CONSERVATIVE"]).mean()),
        "time_exit_fraction":float(x["exit_type"].eq("TIME").mean()),
        "gap_stop_fraction":float(gap.mean()),
        "mean_stop_slippage_r":float(pd.to_numeric(x.loc[gap,"stop_slippage_r"],errors="coerce").mean()) if gap.any() else 0.0,
        "tail_1pct_r":float(r.quantile(.01)),
        "tail_5pct_r":float(r.quantile(.05)),
        "equal_symbol_mean_r":float(sym.mean()) if len(sym) else np.nan,
        "positive_symbol_fraction":float((sym>0).mean()) if len(sym) else np.nan,
        "top10_abs_contribution_fraction":float(contrib.head(10).sum()/denom) if denom>0 else np.nan,
    }


def _nonoverlap(frame:pd.DataFrame)->pd.DataFrame:
    keep=[]
    for _,g in frame.sort_values(["symbol","entry_date"]).groupby("symbol",sort=False):
        last=None
        for idx,row in g.iterrows():
            d=pd.Timestamp(row["entry_date"])
            if last is None or (d-last).days>=84:
                keep.append(idx);last=d
    return frame.loc[keep]


def evaluate_prospective(cfg:ManagementShadowConfig)->dict[str,Any]:
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
    m=_metrics(frame);nm=_metrics(_nonoverlap(frame))

    month=[]
    for period,g in frame.groupby(frame["market_as_of_date"].dt.to_period("M")):
        mm=_metrics(g)
        month.append({"month":str(period),"n":mm.get("n",0),"mean_r":mm.get("mean_r"),"positive":bool(mm.get("mean_r",0)>0)})
    positive_month_fraction=float(np.mean([x["positive"] for x in month])) if month else np.nan

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
        "population":POPULATION,"entry_policy":ENTRY_POLICY,
        "target_atr":TARGET_ATR,"stop_atr":STOP_ATR,"horizon_sessions":HORIZON_SESSIONS,
        "matured_observations":m.get("n",0),"matured_symbols":m.get("symbols",0),
        "metrics":m,"nonoverlap_metrics":nm,
        "positive_month_fraction":positive_month_fraction,"month_evidence":month,
        "frozen_gates":FROZEN_GATES,"gate_results":gates,
        "certification_verdict":verdict,
        "historical_retuning_performed":False,"automatic_retraining":False,
        "production_authority_effect":False,"production_management_effect":False,
    }
    _atomic_json(summary_path,summary)
    return summary


def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.26.2 prospective executable management geometry shadow")
    p.add_argument("--project-root",required=True)
    p.add_argument("--action",choices=("freeze","record","update","evaluate"),default="record")
    return p


def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    root=Path(a.project_root).expanduser().resolve()
    cfg=ManagementShadowConfig(project_root=str(root))
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
