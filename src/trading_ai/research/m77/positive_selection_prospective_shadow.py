from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

VERSION = "M77.24.1-FROZEN-PROSPECTIVE-POSITIVE-SELECTION-SHADOW-1.0"
PROTOCOL_ID = "PSVE-CANDIDATE-001"
PROSPECTIVE_NOT_BEFORE = date(2026, 8, 27)
HORIZON_SESSIONS = 60
TOP_FRACTION = 0.10
SELECTOR = "PROBABILITY_UP"
POPULATION = "TRADE_BUILDER_READY_LONG_AND_DRVE_PASS"

DEFAULT_DRVE_AUTHORITY = "data/downside_risk_veto/current_authority.json"
DEFAULT_ROOT = "data/positive_selection_shadow"
DEFAULT_LEDGER = "data/positive_selection_shadow/prospective_ledger.json"
DEFAULT_SUMMARY = "data/positive_selection_shadow/prospective_certification_summary.json"

FROZEN_GATES = {
    "minimum_selected_observations": 300,
    "minimum_unique_selected_symbols": 100,
    "minimum_win_rate_uplift": 0.03,
    "minimum_mean_return_uplift": 0.0075,
    "maximum_loss_10_rate_change": 0.0,
    "minimum_nonoverlap_win_rate_uplift": 0.02,
    "minimum_equal_symbol_mean_return_uplift": 0.0,
    "maximum_top10_abs_contribution_fraction": 0.35,
    "minimum_positive_month_fraction": 0.70,
}


class ProspectiveShadowError(RuntimeError):
    pass


@dataclass(frozen=True)
class ShadowConfig:
    project_root: str
    authority_path: str = DEFAULT_DRVE_AUTHORITY
    shadow_root: str = DEFAULT_ROOT
    ledger_path: str = DEFAULT_LEDGER
    summary_path: str = DEFAULT_SUMMARY


def _resolve(root: Path, p: str) -> Path:
    q=Path(p)
    return q if q.is_absolute() else root/q


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    os.replace(tmp,path)


def _f(v: Any) -> float | None:
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _freeze_cross_section(authority: dict[str, Any]) -> list[dict[str, Any]]:
    records=authority.get("records") or {}
    rows=[]
    for symbol,rec in records.items():
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
        })
    if not rows:
        return []
    frame=pd.DataFrame(rows).sort_values(["probability_up","symbol"],ascending=[False,True]).reset_index(drop=True)
    frame["positive_selection_rank"]=np.arange(1,len(frame)+1)
    frame["positive_selection_percentile"]=frame["positive_selection_rank"]/len(frame)
    selected_n=max(1,int(math.ceil(len(frame)*TOP_FRACTION)))
    frame["selected_top10"]=frame["positive_selection_rank"]<=selected_n
    return frame.to_dict(orient="records")


def record_shadow_snapshot(cfg: ShadowConfig) -> dict[str, Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    authority_path=_resolve(root,cfg.authority_path)
    if not authority_path.exists():
        raise ProspectiveShadowError(f"DRVE authority missing: {authority_path}")
    authority=_read_json(authority_path)
    if authority.get("feature_parity_valid") is not True:
        raise ProspectiveShadowError("DRVE authority feature parity is not valid")
    if authority.get("production_scope")!="TRADE_BUILDER_READY_LONG_ONLY":
        raise ProspectiveShadowError("Unexpected DRVE production scope")

    market_date=date.fromisoformat(str(authority["market_as_of_date"]))
    if market_date < PROSPECTIVE_NOT_BEFORE:
        return {
            "status":"SKIPPED_PRE_BOUNDARY",
            "market_as_of_date":market_date.isoformat(),
            "prospective_not_before":PROSPECTIVE_NOT_BEFORE.isoformat(),
            "production_authority_effect":False,
        }

    shadow_root=_resolve(root,cfg.shadow_root)
    snap_path=shadow_root/"snapshots"/f"{market_date.isoformat()}.json"
    if snap_path.exists():
        existing=_read_json(snap_path)
        return {
            "status":"ALREADY_FROZEN",
            "market_as_of_date":market_date.isoformat(),
            "stock_scanner_run_id":existing.get("stock_scanner_run_id"),
            "candidate_count":existing.get("candidate_count",0),
            "selected_count":existing.get("selected_count",0),
            "production_authority_effect":False,
        }

    rows=_freeze_cross_section(authority)
    selected=sum(1 for r in rows if r["selected_top10"])
    payload={
        "version":VERSION,
        "protocol_id":PROTOCOL_ID,
        "frozen_at":datetime.now(timezone.utc).isoformat(),
        "market_as_of_date":market_date.isoformat(),
        "stock_scanner_run_id":authority.get("stock_scanner_run_id"),
        "source_authority_generated_at":authority.get("generated_at"),
        "source_model_fingerprint":authority.get("model_fingerprint"),
        "population":POPULATION,
        "selector":SELECTOR,
        "top_fraction":TOP_FRACTION,
        "horizon_sessions":HORIZON_SESSIONS,
        "candidate_count":len(rows),
        "selected_count":selected,
        "records":rows,
        "immutable_first_snapshot_per_market_date":True,
        "production_authority_effect":False,
        "production_ranking_effect":False,
        "production_eligibility_effect":False,
        "automatic_retraining":False,
    }
    _atomic_json(snap_path,payload)
    return {
        "status":"FROZEN",
        "market_as_of_date":market_date.isoformat(),
        "stock_scanner_run_id":payload["stock_scanner_run_id"],
        "candidate_count":len(rows),
        "selected_count":selected,
        "snapshot_path":str(snap_path.relative_to(root)),
        "production_authority_effect":False,
    }


def _load_price_history(root: Path, symbols: set[str], first_date: date) -> dict[str,list[tuple[date,float]]]:
    from trading_ai.database.session import SessionLocal
    from sqlalchemy import text
    session=SessionLocal()
    try:
        bind=session.get_bind()
        if not symbols:
            return {}
        cols=session.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='price_history'
        """)).scalars().all()
        colset={str(c) for c in cols}
        date_col=next((c for c in ("session_date","date","market_date","timestamp") if c in colset),None)
        if date_col is None:
            raise ProspectiveShadowError(
                "price_history has no supported session date column "
                "(expected session_date/date/market_date/timestamp)"
            )
        if "symbol" not in colset or "close" not in colset:
            raise ProspectiveShadowError("price_history missing required symbol/close columns")
        # Column name comes only from the inspected allow-list above.
        stmt=text(f"""
            SELECT symbol, {date_col} AS session_date, close
            FROM price_history
            WHERE symbol = ANY(:symbols)
              AND {date_col} >= :first_date
            ORDER BY symbol, {date_col}
        """)
        rows=session.execute(stmt,{"symbols":sorted(symbols),"first_date":first_date}).mappings().all()
    finally:
        session.close()
    out={}
    for r in rows:
        sym=str(r["symbol"]).upper()
        try:
            d=r["session_date"]
            if isinstance(d,datetime): d=d.date()
            elif not isinstance(d,date): d=date.fromisoformat(str(d))
            c=float(r["close"])
            if math.isfinite(c) and c>0:
                out.setdefault(sym,[]).append((d,c))
        except Exception:
            continue
    # Deduplicate sessions deterministically, last value wins.
    for sym,vals in list(out.items()):
        by={}
        for d,c in vals: by[d]=c
        out[sym]=sorted(by.items())
    return out


def _mature_record(symbol: str, asof: date, history: dict[str,list[tuple[date,float]]]) -> dict[str,Any] | None:
    vals=history.get(symbol) or []
    dates=[x[0] for x in vals]
    # exact as-of session is required to preserve PIT semantics
    try:
        i=dates.index(asof)
    except ValueError:
        return None
    j=i+HORIZON_SESSIONS
    if j>=len(vals):
        return None
    entry=vals[i][1]
    exit_=vals[j][1]
    r=exit_/entry-1.0
    window=[c for _,c in vals[i:j+1]]
    return {
        "entry_close":entry,
        "exit_close_60":exit_,
        "outcome_date":vals[j][0].isoformat(),
        "return_60":r,
        "win":r>0,
        "loss_10":r<=-0.10,
        "loss_20":r<=-0.20,
        "mfe_60":max(window)/entry-1.0,
        "mae_60":min(window)/entry-1.0,
    }


def update_matured_outcomes(cfg: ShadowConfig) -> dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    shadow_root=_resolve(root,cfg.shadow_root)
    snaps=sorted((shadow_root/"snapshots").glob("*.json")) if (shadow_root/"snapshots").exists() else []
    if not snaps:
        summary=evaluate_prospective(cfg)
        return {"status":"NO_SNAPSHOTS","matured_new":0,**summary}

    parsed=[_read_json(p) for p in snaps]
    all_symbols={str(r["symbol"]).upper() for s in parsed for r in (s.get("records") or [])}
    first=min(date.fromisoformat(s["market_as_of_date"]) for s in parsed)
    histories=_load_price_history(root,all_symbols,first)

    ledger_path=_resolve(root,cfg.ledger_path)
    ledger=_read_json(ledger_path) if ledger_path.exists() else {
        "version":VERSION,"protocol_id":PROTOCOL_ID,"records":{},
        "production_authority_effect":False,"automatic_retraining":False,
    }
    recs=ledger.setdefault("records",{})
    new_count=0
    for snap in parsed:
        asof=date.fromisoformat(snap["market_as_of_date"])
        for r in snap.get("records") or []:
            key=f"{asof.isoformat()}|{str(r['symbol']).upper()}"
            if key in recs:
                continue
            matured=_mature_record(str(r["symbol"]).upper(),asof,histories)
            if matured is None:
                continue
            recs[key]={
                "market_as_of_date":asof.isoformat(),
                "symbol":str(r["symbol"]).upper(),
                "probability_up":r["probability_up"],
                "positive_selection_rank":r["positive_selection_rank"],
                "positive_selection_percentile":r["positive_selection_percentile"],
                "selected_top10":bool(r["selected_top10"]),
                **matured,
            }
            new_count+=1
    ledger["updated_at"]=datetime.now(timezone.utc).isoformat()
    _atomic_json(ledger_path,ledger)
    summary=evaluate_prospective(cfg)
    return {"status":"COMPLETE","matured_new":new_count,**summary}


def _nonoverlap(frame: pd.DataFrame) -> pd.DataFrame:
    keep=[]
    for _,g in frame.sort_values(["symbol","market_as_of_date"]).groupby("symbol",sort=False):
        last=None
        for idx,r in g.iterrows():
            d=pd.Timestamp(r["market_as_of_date"])
            if last is None or (d-last).days>=84:  # ~60 trading sessions
                keep.append(idx);last=d
    return frame.loc[keep]


def _metrics(frame: pd.DataFrame) -> dict[str,float|int]:
    if frame.empty:
        return {"n":0}
    r=pd.to_numeric(frame["return_60"],errors="coerce").dropna()
    f=frame.loc[r.index]
    sym=f.assign(_r=r).groupby("symbol")["_r"].mean()
    return {
        "n":int(len(r)),
        "symbols":int(f["symbol"].nunique()),
        "win_rate":float((r>0).mean()),
        "mean_return":float(r.mean()),
        "loss_10_rate":float((r<=-0.10).mean()),
        "loss_20_rate":float((r<=-0.20).mean()),
        "equal_symbol_mean_return":float(sym.mean()) if len(sym) else np.nan,
    }


def evaluate_prospective(cfg: ShadowConfig) -> dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    ledger_path=_resolve(root,cfg.ledger_path)
    summary_path=_resolve(root,cfg.summary_path)
    records=(_read_json(ledger_path).get("records") or {}) if ledger_path.exists() else {}
    frame=pd.DataFrame(list(records.values()))
    if frame.empty:
        summary={
            "version":VERSION,"protocol_id":PROTOCOL_ID,"status":"ACCUMULATING",
            "matured_candidate_observations":0,"matured_selected_observations":0,
            "certification_verdict":"NOT_ENOUGH_PROSPECTIVE_EVIDENCE",
            "frozen_gates":FROZEN_GATES,"production_authority_effect":False,
        }
        _atomic_json(summary_path,summary)
        return summary

    frame["market_as_of_date"]=pd.to_datetime(frame["market_as_of_date"])
    base=_metrics(frame)
    sel=frame[frame["selected_top10"]==True].copy()
    sm=_metrics(sel)
    non=_metrics(_nonoverlap(sel))

    bysym=sel.groupby("symbol")["return_60"].sum().abs().sort_values(ascending=False)
    denom=float(bysym.sum())
    top10_frac=float(bysym.head(10).sum()/denom) if denom>0 else np.nan

    month_rows=[]
    for period,g in frame.groupby(frame["market_as_of_date"].dt.to_period("M")):
        sg=g[g["selected_top10"]==True]
        if len(sg)==0: continue
        b=_metrics(g);s=_metrics(sg)
        month_rows.append({
            "month":str(period),
            "positive":bool(
                s.get("win_rate",np.nan)>b.get("win_rate",np.nan)
                and s.get("mean_return",np.nan)>b.get("mean_return",np.nan)
            ),
        })
    positive_month_fraction=float(np.mean([x["positive"] for x in month_rows])) if month_rows else np.nan

    win_uplift=sm.get("win_rate",np.nan)-base.get("win_rate",np.nan)
    ret_uplift=sm.get("mean_return",np.nan)-base.get("mean_return",np.nan)
    loss10_change=sm.get("loss_10_rate",np.nan)-base.get("loss_10_rate",np.nan)
    non_win_uplift=non.get("win_rate",np.nan)-base.get("win_rate",np.nan)
    eqsym_uplift=sm.get("equal_symbol_mean_return",np.nan)-base.get("equal_symbol_mean_return",np.nan)

    gates={
        "minimum_selected_observations":sm.get("n",0)>=FROZEN_GATES["minimum_selected_observations"],
        "minimum_unique_selected_symbols":sm.get("symbols",0)>=FROZEN_GATES["minimum_unique_selected_symbols"],
        "minimum_win_rate_uplift":bool(np.isfinite(win_uplift) and win_uplift>=FROZEN_GATES["minimum_win_rate_uplift"]),
        "minimum_mean_return_uplift":bool(np.isfinite(ret_uplift) and ret_uplift>=FROZEN_GATES["minimum_mean_return_uplift"]),
        "maximum_loss_10_rate_change":bool(np.isfinite(loss10_change) and loss10_change<=FROZEN_GATES["maximum_loss_10_rate_change"]),
        "minimum_nonoverlap_win_rate_uplift":bool(np.isfinite(non_win_uplift) and non_win_uplift>=FROZEN_GATES["minimum_nonoverlap_win_rate_uplift"]),
        "minimum_equal_symbol_mean_return_uplift":bool(np.isfinite(eqsym_uplift) and eqsym_uplift>FROZEN_GATES["minimum_equal_symbol_mean_return_uplift"]),
        "maximum_top10_abs_contribution_fraction":bool(np.isfinite(top10_frac) and top10_frac<=FROZEN_GATES["maximum_top10_abs_contribution_fraction"]),
        "minimum_positive_month_fraction":bool(np.isfinite(positive_month_fraction) and positive_month_fraction>=FROZEN_GATES["minimum_positive_month_fraction"]),
    }
    enough=sm.get("n",0)>=FROZEN_GATES["minimum_selected_observations"] and sm.get("symbols",0)>=FROZEN_GATES["minimum_unique_selected_symbols"]
    verdict="PASS" if enough and all(gates.values()) else ("FAIL" if enough else "NOT_ENOUGH_PROSPECTIVE_EVIDENCE")
    summary={
        "version":VERSION,"protocol_id":PROTOCOL_ID,"status":"COMPLETE",
        "selector":SELECTOR,"top_fraction":TOP_FRACTION,"horizon_sessions":HORIZON_SESSIONS,
        "population":POPULATION,
        "matured_candidate_observations":base.get("n",0),
        "matured_selected_observations":sm.get("n",0),
        "matured_selected_symbols":sm.get("symbols",0),
        "baseline_metrics":base,"selected_metrics":sm,"nonoverlap_selected_metrics":non,
        "win_rate_uplift":win_uplift,"mean_return_uplift":ret_uplift,
        "loss_10_rate_change":loss10_change,"nonoverlap_win_rate_uplift":non_win_uplift,
        "equal_symbol_mean_return_uplift":eqsym_uplift,
        "top10_abs_contribution_fraction":top10_frac,
        "positive_month_fraction":positive_month_fraction,
        "month_evidence":month_rows,
        "frozen_gates":FROZEN_GATES,"gate_results":gates,
        "certification_verdict":verdict,
        "production_authority_effect":False,
        "production_ranking_effect":False,
        "production_eligibility_effect":False,
        "automatic_retraining":False,
        "historical_retuning_performed":False,
    }
    _atomic_json(summary_path,summary)
    return summary


def write_frozen_protocol(root: Path) -> Path:
    path=root/DEFAULT_ROOT/"FROZEN_PROSPECTIVE_PROTOCOL.json"
    payload={
        "version":"M77.24.1-FROZEN-PROSPECTIVE-PROTOCOL-1.0",
        "protocol_id":PROTOCOL_ID,
        "frozen_at":datetime.now(timezone.utc).isoformat(),
        "prospective_not_before":PROSPECTIVE_NOT_BEFORE.isoformat(),
        "population":POPULATION,
        "selector":SELECTOR,
        "top_fraction":TOP_FRACTION,
        "horizon_sessions":HORIZON_SESSIONS,
        "frozen_gates":FROZEN_GATES,
        "one_immutable_snapshot_per_market_date":True,
        "historical_2018_2026_forbidden_for_tuning":True,
        "production_authority_effect":False,
        "production_ranking_effect":False,
        "production_eligibility_effect":False,
        "automatic_retraining":False,
    }
    if path.exists():
        existing=_read_json(path)
        invariant={k:existing.get(k) for k in payload if k!="frozen_at"}
        wanted={k:payload.get(k) for k in payload if k!="frozen_at"}
        if invariant!=wanted:
            raise ProspectiveShadowError("Frozen prospective protocol mismatch; refusing overwrite")
        return path
    _atomic_json(path,payload)
    return path


def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.24.1 frozen prospective positive-selection shadow certification")
    p.add_argument("--project-root",required=True)
    p.add_argument("--action",choices=("record","update","evaluate","freeze"),default="record")
    return p


def main(argv: list[str] | None=None) -> int:
    a=build_parser().parse_args(argv)
    cfg=ShadowConfig(project_root=a.project_root)
    root=Path(a.project_root).expanduser().resolve()
    write_frozen_protocol(root)
    if a.action=="record": result=record_shadow_snapshot(cfg)
    elif a.action=="update": result=update_matured_outcomes(cfg)
    elif a.action=="evaluate": result=evaluate_prospective(cfg)
    else: result={"status":"FROZEN","protocol_path":str((root/DEFAULT_ROOT/"FROZEN_PROSPECTIVE_PROTOCOL.json").relative_to(root))}
    print(json.dumps(result,indent=2,sort_keys=True,default=str))
    return 0
