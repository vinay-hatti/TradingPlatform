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

def _simulate_executable(
    future: pd.DataFrame,
    entry: float,
    atr: float,
    target_atr: float,
    stop_atr: float,
    horizon_close: float,
) -> dict[str, Any]:
    target=entry+target_atr*atr
    stop=entry-stop_atr*atr
    risk=stop_atr*atr
    if risk <= 0:
        raise ExecutableGeometryError("Non-positive initial risk")

    for day_no,(_,bar) in enumerate(future.iterrows(),start=1):
        o=float(bar["open"]); h=float(bar["high"]); l=float(bar["low"])
        # Opening price is ordered before the intraday high/low.
        if math.isfinite(o) and o <= stop:
            exit_px=o
            r=(exit_px-entry)/risk
            return {
                "exit_type":"STOP_GAP","exit_day":day_no,"exit_price":exit_px,"r_multiple":r,
                "gap_stop":True,"stop_slippage_r":r+1.0,"ambiguous_bar":False,
            }
        if math.isfinite(o) and o >= target:
            exit_px=target
            return {
                "exit_type":"TARGET_GAP","exit_day":day_no,"exit_price":exit_px,
                "r_multiple":target_atr/stop_atr,"gap_stop":False,
                "stop_slippage_r":0.0,"ambiguous_bar":False,
            }

        hit_target=math.isfinite(h) and h>=target
        hit_stop=math.isfinite(l) and l<=stop
        if hit_target and hit_stop:
            # Daily OHLC cannot establish intraday order. Primary executable
            # estimate is deliberately pessimistic.
            exit_px=stop
            return {
                "exit_type":"AMBIGUOUS_STOP_CONSERVATIVE","exit_day":day_no,"exit_price":exit_px,
                "r_multiple":-1.0,"gap_stop":False,"stop_slippage_r":0.0,"ambiguous_bar":True,
            }
        if hit_stop:
            return {
                "exit_type":"STOP","exit_day":day_no,"exit_price":stop,"r_multiple":-1.0,
                "gap_stop":False,"stop_slippage_r":0.0,"ambiguous_bar":False,
            }
        if hit_target:
            return {
                "exit_type":"TARGET","exit_day":day_no,"exit_price":target,
                "r_multiple":target_atr/stop_atr,"gap_stop":False,
                "stop_slippage_r":0.0,"ambiguous_bar":False,
            }

    exit_px=float(horizon_close)
    return {
        "exit_type":"TIME","exit_day":len(future),"exit_price":exit_px,
        "r_multiple":(exit_px-entry)/risk,"gap_stop":False,
        "stop_slippage_r":0.0,"ambiguous_bar":False,
    }


def _process_symbol(args: tuple[str,str,str]) -> tuple[str,list[dict[str,Any]],str|None]:
    symbol,raw_path,candidate_json=args
    try:
        cand=pd.read_json(StringIO(candidate_json),orient="records")
        cand["as_of"]=pd.to_datetime(cand["as_of"])
        df=read_daily_file(Path(raw_path),DEVELOPMENT_END.date().isoformat())
        if len(df)<320:
            return symbol,[],"INSUFFICIENT_HISTORY"
        df=engineer_ohlcv_features(df)
        by_date={pd.Timestamp(d).normalize():i for i,d in enumerate(df["as_of"])}
        rows=[]
        for _,cr in cand.iterrows():
            d=pd.Timestamp(cr["as_of"]).normalize()
            i=by_date.get(d)
            if i is None or i+1>=len(df):
                continue
            atr=float(df.iloc[i].get("atr_14",np.nan))
            if not math.isfinite(atr) or atr<=0:
                continue
            entry_idx=i+1
            entry=float(df.iloc[entry_idx]["open"])
            if not math.isfinite(entry) or entry<=0:
                continue

            base={
                "symbol":symbol,"as_of":d,"entry_date":df.iloc[entry_idx]["as_of"],
                "entry_price":entry,"candidate_atr":atr,
                "probability_up":cr.get("probability_up"),"bearish_rank_pct":cr.get("bearish_rank_pct"),
                "overall_score":cr.get("score_overall",cr.get("overall_score")),
                "idi_trade_quality":cr.get("idi_trade_quality"),
                "score_options_suitability":cr.get("score_options_suitability"),
            }

            for horizon in HORIZONS:
                terminal=entry_idx+horizon
                if terminal>=len(df):
                    continue
                # Like M77.26, entry day is excluded. The first monitored bar is
                # the next session, avoiding unobservable next-open intraday order.
                future=df.iloc[entry_idx+1:terminal+1]
                horizon_close=float(df.iloc[terminal]["close"])
                for target in TARGET_ATR:
                    for stop in STOP_ATR:
                        sim=_simulate_executable(future,entry,atr,target,stop,horizon_close)
                        rows.append({
                            **base,"horizon":horizon,"target_atr":target,"stop_atr":stop,
                            **sim,
                        })
        if not rows:
            return symbol,[],"NO_CANDIDATE_DATES_MATCHED_RAW_SESSIONS"
        return symbol,rows,None
    except Exception as exc:
        return symbol,[],f"{type(exc).__name__}: {exc}"


def build_executable_panel(
    cfg: ExecutableGeometryConfig,
    candidates: pd.DataFrame,
) -> tuple[pd.DataFrame,pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    paths=_discover(_resolve(root,cfg.daily_root))
    tasks=[];unmatched=[]
    for symbol,g in candidates.groupby("symbol",sort=False):
        symbol=str(symbol)
        p=paths.get(symbol)
        if p is None:
            unmatched.append(symbol)
            continue
        tasks.append((symbol,str(p),g.to_json(orient="records",date_format="iso")))
    if not tasks:
        raise ExecutableGeometryError("No candidate symbols matched daily authority")

    rows=[];fails=[]
    if cfg.workers<=1:
        results=map(_process_symbol,tasks)
        for sym,r,e in results:
            rows.extend(r)
            if e:fails.append({"symbol":sym,"error":e})
    else:
        with ProcessPoolExecutor(max_workers=cfg.workers) as ex:
            futs=[ex.submit(_process_symbol,t) for t in tasks]
            for fut in as_completed(futs):
                sym,r,e=fut.result()
                rows.extend(r)
                if e:fails.append({"symbol":sym,"error":e})

    panel=pd.DataFrame(rows)
    if panel.empty:
        counts={}
        for x in fails:
            counts[x["error"]]=counts.get(x["error"],0)+1
        raise ExecutableGeometryError(
            f"No executable observations materialized; failures={sorted(counts.items(),key=lambda x:-x[1])[:10]}"
        )
    panel["as_of"]=pd.to_datetime(panel["as_of"])
    panel["entry_date"]=pd.to_datetime(panel["entry_date"])
    diag={
        "daily_files_discovered":len(paths),
        "candidate_symbols":int(candidates["symbol"].nunique()),
        "matched_candidate_symbols":len(tasks),
        "unmatched_candidate_symbols":len(unmatched),
        "unmatched_candidate_symbol_sample":sorted(unmatched)[:50],
    }
    return panel,pd.DataFrame(fails),diag


def _metrics(g: pd.DataFrame) -> dict[str,Any]:
    r=pd.to_numeric(g["r_multiple"],errors="coerce").dropna()
    if r.empty:
        return {"n":0}
    x=g.loc[r.index].copy()
    wins=r>0
    losses=r<0
    gross_profit=float(r[r>0].sum())
    gross_loss=float(-r[r<0].sum())
    sym=x.assign(_r=r).groupby("symbol")["_r"].mean()
    contrib=x.assign(_r=r).groupby("symbol")["_r"].sum().abs().sort_values(ascending=False)
    denom=float(contrib.sum())
    stop_mask=x["exit_type"].isin(["STOP","STOP_GAP","AMBIGUOUS_STOP_CONSERVATIVE"])
    target_mask=x["exit_type"].isin(["TARGET","TARGET_GAP"])
    time_mask=x["exit_type"].eq("TIME")
    gap=x["exit_type"].eq("STOP_GAP")
    return {
        "n":int(len(r)),"symbols":int(x["symbol"].nunique()),
        "mean_r":float(r.mean()),"median_r":float(r.median()),
        "win_rate":float(wins.mean()),
        "loss_rate":float(losses.mean()),
        "profit_factor":float(gross_profit/gross_loss) if gross_loss>0 else np.inf,
        "target_exit_fraction":float(target_mask.mean()),
        "stop_exit_fraction":float(stop_mask.mean()),
        "time_exit_fraction":float(time_mask.mean()),
        "ambiguous_fraction":float(x["ambiguous_bar"].fillna(False).mean()),
        "gap_stop_fraction":float(gap.mean()),
        "mean_stop_slippage_r":float(pd.to_numeric(x.loc[gap,"stop_slippage_r"],errors="coerce").mean()) if gap.any() else 0.0,
        "mean_time_exit_r":float(pd.to_numeric(x.loc[time_mask,"r_multiple"],errors="coerce").mean()) if time_mask.any() else np.nan,
        "tail_loss_5pct_r":float(r.quantile(0.05)),
        "tail_loss_1pct_r":float(r.quantile(0.01)),
        "equal_symbol_mean_r":float(sym.mean()) if len(sym) else np.nan,
        "positive_symbol_fraction":float((sym>0).mean()) if len(sym) else np.nan,
        "largest_symbol_abs_contribution_fraction":float(contrib.iloc[0]/denom) if denom>0 else np.nan,
        "top10_symbol_abs_contribution_fraction":float(contrib.head(10).sum()/denom) if denom>0 else np.nan,
    }


def executable_evidence(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    rows=[];years=[];non=[]
    for (h,target,stop),g in panel.groupby(["horizon","target_atr","stop_atr"],sort=True):
        m=_metrics(g)
        rows.append({"horizon":int(h),"target_atr":float(target),"stop_atr":float(stop),**m})
        for year,yg in g.groupby(g["as_of"].dt.year):
            years.append({
                "horizon":int(h),"target_atr":float(target),"stop_atr":float(stop),"year":int(year),
                **_metrics(yg),
            })
        keep=[]
        for _,sg in g.sort_values(["symbol","entry_date"]).groupby("symbol",sort=False):
            last=None
            for idx,row in sg.iterrows():
                d=pd.Timestamp(row["entry_date"])
                if last is None or (d-last).days>=math.ceil(int(h)*7/5):
                    keep.append(idx);last=d
        nm=_metrics(g.loc[keep]) if keep else {"n":0}
        non.append({"horizon":int(h),"target_atr":float(target),"stop_atr":float(stop),**nm})
    return pd.DataFrame(rows),pd.DataFrame(years),pd.DataFrame(non)


def _max_drawdown_proxy(g:pd.DataFrame)->float:
    # Research proxy: sequential cumulative R by candidate as-of. It is not a
    # capital-overlap portfolio simulation, so it is labeled explicitly.
    z=g.sort_values(["as_of","symbol"])
    r=pd.to_numeric(z["r_multiple"],errors="coerce").fillna(0.0).to_numpy()
    curve=np.cumsum(r)
    peak=np.maximum.accumulate(np.r_[0.0,curve])
    dd=np.r_[0.0,curve]-peak
    return float(dd.min())


def robustness(panel:pd.DataFrame,evidence:pd.DataFrame)->pd.DataFrame:
    rows=[]
    for _,e in evidence.iterrows():
        g=panel[
            (panel["horizon"]==int(e["horizon"]))
            & (panel["target_atr"]==float(e["target_atr"]))
            & (panel["stop_atr"]==float(e["stop_atr"]))
        ]
        rows.append({
            "horizon":int(e["horizon"]),"target_atr":float(e["target_atr"]),"stop_atr":float(e["stop_atr"]),
            "sequential_max_drawdown_proxy_r":_max_drawdown_proxy(g),
        })
    return pd.DataFrame(rows)


def readiness(evidence:pd.DataFrame,years:pd.DataFrame,nonoverlap:pd.DataFrame)->pd.DataFrame:
    y=years.assign(
        positive=lambda x:(x["mean_r"]>0)&(x["profit_factor"]>1.0)
    ).groupby(["horizon","target_atr","stop_atr"])["positive"].agg(["sum","count"]).reset_index()
    y["positive_year_fraction"]=y["sum"]/y["count"].replace(0,np.nan)

    n=nonoverlap[[
        "horizon","target_atr","stop_atr","n","mean_r","profit_factor","equal_symbol_mean_r"
    ]].rename(columns={
        "n":"nonoverlap_n","mean_r":"nonoverlap_mean_r",
        "profit_factor":"nonoverlap_profit_factor",
        "equal_symbol_mean_r":"nonoverlap_equal_symbol_mean_r",
    })
    out=evidence.merge(
        y[["horizon","target_atr","stop_atr","positive_year_fraction"]],
        on=["horizon","target_atr","stop_atr"],how="left"
    ).merge(n,on=["horizon","target_atr","stop_atr"],how="left")

    # Frozen executable selection gates: broad, positive full-cohort economics,
    # year/non-overlap stability, limited gap dependence and concentration.
    out["gate_n"]=out["n"]>=5000
    out["gate_symbols"]=out["symbols"]>=400
    out["gate_mean_r"]=out["mean_r"]>=0.08
    out["gate_profit_factor"]=out["profit_factor"]>=1.15
    out["gate_equal_symbol"]=out["equal_symbol_mean_r"]>=0.05
    out["gate_positive_symbols"]=out["positive_symbol_fraction"]>=0.55
    out["gate_positive_years"]=out["positive_year_fraction"]>=0.80
    out["gate_nonoverlap"]=out["nonoverlap_mean_r"]>=0.05
    out["gate_nonoverlap_pf"]=out["nonoverlap_profit_factor"]>=1.10
    out["gate_concentration"]=out["top10_symbol_abs_contribution_fraction"]<=0.25
    out["gate_gap_sensitivity"]=out["gap_stop_fraction"]<=0.08
    out["gate_tail_loss"]=out["tail_loss_1pct_r"]>=-2.50
    gates=[c for c in out.columns if c.startswith("gate_")]
    out["development_ready_executable"]=out[gates].all(axis=1)

    # Frozen ranking, used only after gates. It does not simply maximize mean R.
    # Prefer stable economics, breadth, lower gap dependence and lower concentration.
    out["robustness_score"]=(
        out["mean_r"].clip(-1,1)
        +0.30*(out["profit_factor"].clip(0,3)-1.0)
        +0.20*out["positive_year_fraction"].fillna(0)
        +0.15*out["nonoverlap_mean_r"].clip(-1,1)
        +0.10*out["equal_symbol_mean_r"].clip(-1,1)
        -0.20*out["gap_stop_fraction"].fillna(1)
        -0.20*out["top10_symbol_abs_contribution_fraction"].fillna(1)
    )
    return out.sort_values(
        ["development_ready_executable","robustness_score","mean_r"],
        ascending=[False,False,False]
    ).reset_index(drop=True)


def run_lab(cfg:ExecutableGeometryConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    candidates,meta=load_candidates(cfg)
    panel,fails,diag=build_executable_panel(cfg,candidates)
    evidence,years,non=executable_evidence(panel)
    robust=robustness(panel,evidence)
    ready=readiness(evidence,years,non).merge(
        robust,on=["horizon","target_atr","stop_atr"],how="left",validate="one_to_one"
    )

    panel.to_csv(outdir/"executable_geometry_observation_panel.csv.gz",index=False,compression="gzip")
    evidence.to_csv(outdir/"executable_geometry_evidence.csv",index=False)
    years.to_csv(outdir/"executable_geometry_year_evidence.csv",index=False)
    non.to_csv(outdir/"executable_geometry_nonoverlap_evidence.csv",index=False)
    robust.to_csv(outdir/"executable_geometry_drawdown_proxy.csv",index=False)
    ready.to_csv(outdir/"executable_geometry_readiness.csv",index=False)
    fails.to_csv(outdir/"symbol_failures.csv",index=False)

    best=ready[ready["development_ready_executable"]==True].head(1)
    report=[
        "# M77.26.1 Executable Management Geometry Recalibration","",
        "## Frozen execution semantics","",
        f"- Entry: {ENTRY_POLICY}.",
        f"- Stop gap: {STOP_GAP_POLICY}.",
        f"- Target gap: {TARGET_GAP_POLICY}.",
        f"- Same-bar ambiguity: {AMBIGUITY_POLICY}.",
        f"- Unresolved by horizon: {UNRESOLVED_POLICY}.",
        "- Full-cohort R includes target exits, stop exits, gap stops, conservative ambiguous stops, and time exits.",
        "- 2018-2026 outcomes are not read.","",
        "## Highest-ranked Development-ready executable geometry","",_md(best),"",
        "## Highest-ranked executable geometries","",_md(ready.head(30)),"",
    ]
    (outdir/"EXECUTABLE_MANAGEMENT_GEOMETRY_RECALIBRATION_REPORT.md").write_text("\n".join(report))

    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31","consumed_2018_2026_rows_read":0,
        "entry_policy":ENTRY_POLICY,
        "execution_semantics":{
            "stop_gap":STOP_GAP_POLICY,"target_gap":TARGET_GAP_POLICY,
            "same_bar_ambiguity":AMBIGUITY_POLICY,"unresolved":UNRESOLVED_POLICY,
        },
        "candidate_dates":int(len(candidates)),"candidate_symbols":int(candidates["symbol"].nunique()),
        "observation_rows":int(len(panel)),"geometry_configurations":int(len(evidence)),
        "development_ready_executable_geometries":int(ready["development_ready_executable"].sum()),
        "daily_authority_diagnostics":diag,"symbol_failures":int(len(fails)),
        "frozen_target_grid":list(TARGET_ATR),"frozen_stop_grid":list(STOP_ATR),"frozen_horizons":list(HORIZONS),
        "m77_26_grid_expanded":False,"m77_23_drv_modified":False,"m77_24_1_psve_modified":False,
        "production_authority_effect":False,"polygon_api_called":False,
        "next_step":"REVIEW FULL-COHORT EXECUTABLE GEOMETRY; DO NOT USE CONSUMED 2018-2026 TO RETUNE",
        "upstream_sha256":meta,
    }
    if not best.empty:
        b=best.iloc[0]
        summary["highest_ranked_development_ready_geometry"]={
            "horizon":int(b["horizon"]),"target_atr":float(b["target_atr"]),"stop_atr":float(b["stop_atr"]),
            "mean_r":float(b["mean_r"]),"profit_factor":float(b["profit_factor"]),
            "win_rate":float(b["win_rate"]),"positive_year_fraction":float(b["positive_year_fraction"]),
            "nonoverlap_mean_r":float(b["nonoverlap_mean_r"]),
            "gap_stop_fraction":float(b["gap_stop_fraction"]),
        }
    _atomic_json(outdir/"executable_geometry_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{"version":VERSION,"config":cfg.__dict__,"summary":summary})
    return summary


def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.26.1 Development-only executable management geometry recalibration")
    p.add_argument("--project-root",required=True)
    p.add_argument("--daily-root",default=ExecutableGeometryConfig.daily_root)
    p.add_argument("--prediction-path",default=ExecutableGeometryConfig.prediction_path)
    p.add_argument("--integrity-path",default=ExecutableGeometryConfig.integrity_path)
    p.add_argument("--pit-candidate-path",default=ExecutableGeometryConfig.pit_candidate_path)
    p.add_argument("--output-dir",default=ExecutableGeometryConfig.output_dir)
    p.add_argument("--workers",type=int,default=max(1,min(6,(os.cpu_count() or 4)-1)))
    return p


def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    cfg=ExecutableGeometryConfig(
        project_root=a.project_root,daily_root=a.daily_root,prediction_path=a.prediction_path,
        integrity_path=a.integrity_path,pit_candidate_path=a.pit_candidate_path,
        output_dir=a.output_dir,workers=a.workers,
    )
    print(json.dumps(run_lab(cfg),indent=2,sort_keys=True,default=_json_default))
    return 0

VERSION = "M77.30.0-PROSPECTIVE-CROSS-SECTIONAL-CAPITAL-PRIORITY-SHADOW-1.0"
PROTOCOL_ID = "CPRE-CANDIDATE-001"
PROSPECTIVE_NOT_BEFORE = date(2026, 8, 27)

TOP_K = 3
HORIZON_SESSIONS = 60
TARGET_ATR = 5.0
STOP_ATR = 3.0
ENTRY_POLICY = "NEXT_OPEN"
POPULATION = "TRADE_BUILDER_READY_LONG_AND_DRVE_PASS"
RANKER = "PROBABILITY_UP_DESCENDING"

DEFAULT_DRVE_AUTHORITY = "data/downside_risk_veto/current_authority.json"
DEFAULT_ROOT = "data/cross_sectional_capital_priority_shadow"
DEFAULT_LEDGER = "data/cross_sectional_capital_priority_shadow/prospective_ledger.json"
DEFAULT_SUMMARY = "data/cross_sectional_capital_priority_shadow/prospective_certification_summary.json"

FROZEN_GATES = {
    "minimum_matured_selected_observations": 250,
    "minimum_unique_selected_symbols": 100,
    "minimum_selected_mean_r": 0.20,
    "minimum_selected_profit_factor": 1.40,
    "minimum_mean_r_uplift_vs_same_day_complement": 0.05,
    "minimum_equal_symbol_mean_r": 0.15,
    "minimum_positive_month_fraction": 0.70,
    "minimum_nonoverlap_mean_r": 0.15,
    "minimum_nonoverlap_profit_factor": 1.30,
    "maximum_top10_abs_contribution_fraction": 0.25,
    "maximum_gap_stop_fraction": 0.10,
    "minimum_1pct_tail_r": -2.50,
}

class CapitalPriorityShadowError(RuntimeError):
    pass

@dataclass(frozen=True)
class CapitalPriorityShadowConfig:
    project_root: str
    authority_path: str = DEFAULT_DRVE_AUTHORITY
    shadow_root: str = DEFAULT_ROOT
    ledger_path: str = DEFAULT_LEDGER
    summary_path: str = DEFAULT_SUMMARY


def _eligible_ranked(authority: dict[str,Any]) -> list[dict[str,Any]]:
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
    for i,r in enumerate(rows,start=1):
        r["probability_up_rank"]=i
        r["probability_up_percentile"]=i/n if n else None
        r["selected_top3"]=i<=TOP_K
    return rows


def write_frozen_protocol(root:Path)->Path:
    path=root/DEFAULT_ROOT/"FROZEN_PROSPECTIVE_PROTOCOL.json"
    payload={
        "version":"M77.30-FROZEN-PROSPECTIVE-PROTOCOL-1.0",
        "protocol_id":PROTOCOL_ID,
        "frozen_at":datetime.now(timezone.utc).isoformat(),
        "prospective_not_before":PROSPECTIVE_NOT_BEFORE.isoformat(),
        "population":POPULATION,
        "ranker":RANKER,
        "top_k":TOP_K,
        "tie_break":"SYMBOL_ASCENDING",
        "entry_policy":ENTRY_POLICY,
        "candidate_atr_definition":"WILDER_EWM_ATR14_POINT_IN_TIME",
        "target_atr":TARGET_ATR,
        "stop_atr":STOP_ATR,
        "horizon_sessions":HORIZON_SESSIONS,
        "stop_gap_fill":"OPEN_IF_OPEN_AT_OR_BELOW_STOP",
        "target_gap_fill":"TARGET_PRICE",
        "same_bar_target_stop":"CONSERVATIVE_STOP",
        "unresolved_by_horizon":"EXIT_AT_HORIZON_CLOSE",
        "snapshot_full_eligible_ranked_cohort":True,
        "one_immutable_snapshot_per_market_date":True,
        "same_day_complement_definition":"ELIGIBLE_RANK_4_PLUS",
        "frozen_gates":FROZEN_GATES,
        "historical_2018_2026_forbidden_for_tuning":True,
        "psve_candidate_001_unchanged":True,
        "mge_candidate_001_unchanged":True,
        "cqmi_candidate_001_unchanged":True,
        "production_capital_allocation_effect":False,
        "production_authority_effect":False,
        "automatic_retraining":False,
    }
    if path.exists():
        existing=_read_json(path)
        invariant={k:existing.get(k) for k in payload if k!="frozen_at"}
        wanted={k:payload.get(k) for k in payload if k!="frozen_at"}
        if invariant!=wanted:
            raise CapitalPriorityShadowError("Frozen CPRE protocol mismatch; refusing overwrite")
        return path
    _atomic_json(path,payload)
    return path


def record_shadow_snapshot(cfg:CapitalPriorityShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    authority_path=_resolve(root,cfg.authority_path)
    if not authority_path.exists():
        raise CapitalPriorityShadowError(f"DRVE authority missing: {authority_path}")
    authority=_read_json(authority_path)
    if authority.get("feature_parity_valid") is not True:
        raise CapitalPriorityShadowError("DRVE authority feature parity invalid")
    if authority.get("production_scope")!="TRADE_BUILDER_READY_LONG_ONLY":
        raise CapitalPriorityShadowError("Unexpected DRVE production scope")

    market_date=date.fromisoformat(str(authority["market_as_of_date"]))
    if market_date<PROSPECTIVE_NOT_BEFORE:
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
            "eligible_count":existing.get("eligible_count",0),
            "selected_count":existing.get("selected_count",0),
            "atr_ready_count":existing.get("atr_ready_count",0),
            "production_authority_effect":False,
        }

    ranked=_eligible_ranked(authority)
    symbols={r["symbol"] for r in ranked}
    history=_load_ohlc(root,symbols,market_date-timedelta(days=730),market_date)

    frozen=[];missing=[]
    for rec in ranked:
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
        "population":POPULATION,"ranker":RANKER,"top_k":TOP_K,
        "tie_break":"SYMBOL_ASCENDING",
        "entry_policy":ENTRY_POLICY,"target_atr":TARGET_ATR,"stop_atr":STOP_ATR,
        "horizon_sessions":HORIZON_SESSIONS,
        "eligible_count":len(ranked),
        "selected_count":min(TOP_K,len(ranked)),
        "atr_ready_count":len(frozen),
        "atr_missing_symbols":missing,
        "records":frozen,
        "immutable_first_snapshot_per_market_date":True,
        "full_ranked_cohort_snapshotted":True,
        "psve_candidate_001_unchanged":True,
        "mge_candidate_001_unchanged":True,
        "cqmi_candidate_001_unchanged":True,
        "production_capital_allocation_effect":False,
        "production_authority_effect":False,
        "automatic_retraining":False,
    }
    _atomic_json(snap_path,payload)
    return {
        "status":"FROZEN",
        "market_as_of_date":market_date.isoformat(),
        "stock_scanner_run_id":payload["stock_scanner_run_id"],
        "eligible_count":len(ranked),
        "selected_count":min(TOP_K,len(ranked)),
        "atr_ready_count":len(frozen),
        "atr_missing_count":len(missing),
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


def update_matured_outcomes(cfg:CapitalPriorityShadowConfig)->dict[str,Any]:
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
        "production_authority_effect":False,
        "production_capital_allocation_effect":False,
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
                "market_as_of_date":asof.isoformat(),
                "symbol":sym,
                "candidate_atr":rec["candidate_atr"],
                "probability_up":rec.get("probability_up"),
                "probability_up_rank":rec.get("probability_up_rank"),
                "probability_up_percentile":rec.get("probability_up_percentile"),
                "selected_top3":bool(rec.get("selected_top3")),
                "drve_cross_section_percentile":rec.get("drve_cross_section_percentile"),
                **matured,
            }
            new_count+=1
    ledger["updated_at"]=datetime.now(timezone.utc).isoformat()
    _atomic_json(ledger_path,ledger)
    summary=evaluate_prospective(cfg)
    return {"status":"COMPLETE","matured_new":new_count,**summary}


def _monthly_positive_fraction(frame:pd.DataFrame)->float:
    if frame.empty:
        return np.nan
    vals=[]
    for _,g in frame.groupby(frame["market_as_of_date"].dt.to_period("M")):
        vals.append(float(pd.to_numeric(g["r_multiple"],errors="coerce").mean()>0))
    return float(np.mean(vals)) if vals else np.nan


def _same_day_uplift(frame:pd.DataFrame)->dict[str,Any]:
    rows=[]
    for d,g in frame.groupby("market_as_of_date"):
        sel=g[g["selected_top3"]==True]
        comp=g[g["selected_top3"]==False]
        if sel.empty or comp.empty:
            continue
        rows.append({
            "market_as_of_date":d,
            "selected_n":len(sel),"complement_n":len(comp),
            "selected_mean_r":float(sel["r_multiple"].mean()),
            "complement_mean_r":float(comp["r_multiple"].mean()),
            "uplift_r":float(sel["r_multiple"].mean()-comp["r_multiple"].mean()),
        })
    x=pd.DataFrame(rows)
    if x.empty:
        return {"dates":0}
    weights=np.minimum(x["selected_n"],x["complement_n"]).astype(float)
    return {
        "dates":int(len(x)),
        "equal_date_mean_uplift_r":float(x["uplift_r"].mean()),
        "matched_size_weighted_mean_uplift_r":float(np.average(x["uplift_r"],weights=weights)) if weights.sum()>0 else np.nan,
        "positive_uplift_date_fraction":float((x["uplift_r"]>0).mean()),
    }


def evaluate_prospective(cfg:CapitalPriorityShadowConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    ledger_path=_resolve(root,cfg.ledger_path)
    summary_path=_resolve(root,cfg.summary_path)
    records=(_read_json(ledger_path).get("records") or {}) if ledger_path.exists() else {}
    frame=pd.DataFrame(list(records.values()))
    if frame.empty:
        summary={
            "version":VERSION,"protocol_id":PROTOCOL_ID,"status":"ACCUMULATING",
            "matured_observations":0,"matured_selected_observations":0,
            "matured_selected_symbols":0,
            "certification_verdict":"NOT_ENOUGH_PROSPECTIVE_EVIDENCE",
            "frozen_gates":FROZEN_GATES,
            "production_authority_effect":False,
        }
        _atomic_json(summary_path,summary)
        return summary

    frame["market_as_of_date"]=pd.to_datetime(frame["market_as_of_date"])
    frame["entry_date"]=pd.to_datetime(frame["entry_date"])
    frame["selected_top3"]=frame["selected_top3"].astype(bool)

    selected=frame[frame["selected_top3"]==True].copy()
    complement=frame[frame["selected_top3"]==False].copy()

    sm=_metrics(selected)
    cm=_metrics(complement)
    snm=_metrics(_nonoverlap(selected))
    uplift=_same_day_uplift(frame)
    positive_month_fraction=_monthly_positive_fraction(selected)

    gates={
        "minimum_matured_selected_observations":sm.get("n",0)>=FROZEN_GATES["minimum_matured_selected_observations"],
        "minimum_unique_selected_symbols":sm.get("symbols",0)>=FROZEN_GATES["minimum_unique_selected_symbols"],
        "minimum_selected_mean_r":bool(np.isfinite(sm.get("mean_r",np.nan)) and sm["mean_r"]>=FROZEN_GATES["minimum_selected_mean_r"]),
        "minimum_selected_profit_factor":bool(np.isfinite(sm.get("profit_factor",np.nan)) and sm["profit_factor"]>=FROZEN_GATES["minimum_selected_profit_factor"]),
        "minimum_mean_r_uplift_vs_same_day_complement":bool(
            np.isfinite(uplift.get("matched_size_weighted_mean_uplift_r",np.nan))
            and uplift["matched_size_weighted_mean_uplift_r"]>=FROZEN_GATES["minimum_mean_r_uplift_vs_same_day_complement"]
        ),
        "minimum_equal_symbol_mean_r":bool(np.isfinite(sm.get("equal_symbol_mean_r",np.nan)) and sm["equal_symbol_mean_r"]>=FROZEN_GATES["minimum_equal_symbol_mean_r"]),
        "minimum_positive_month_fraction":bool(np.isfinite(positive_month_fraction) and positive_month_fraction>=FROZEN_GATES["minimum_positive_month_fraction"]),
        "minimum_nonoverlap_mean_r":bool(np.isfinite(snm.get("mean_r",np.nan)) and snm["mean_r"]>=FROZEN_GATES["minimum_nonoverlap_mean_r"]),
        "minimum_nonoverlap_profit_factor":bool(np.isfinite(snm.get("profit_factor",np.nan)) and snm["profit_factor"]>=FROZEN_GATES["minimum_nonoverlap_profit_factor"]),
        "maximum_top10_abs_contribution_fraction":bool(np.isfinite(sm.get("top10_abs_contribution_fraction",np.nan)) and sm["top10_abs_contribution_fraction"]<=FROZEN_GATES["maximum_top10_abs_contribution_fraction"]),
        "maximum_gap_stop_fraction":bool(np.isfinite(sm.get("gap_stop_fraction",np.nan)) and sm["gap_stop_fraction"]<=FROZEN_GATES["maximum_gap_stop_fraction"]),
        "minimum_1pct_tail_r":bool(np.isfinite(sm.get("tail_1pct_r",np.nan)) and sm["tail_1pct_r"]>=FROZEN_GATES["minimum_1pct_tail_r"]),
    }

    enough=gates["minimum_matured_selected_observations"] and gates["minimum_unique_selected_symbols"]
    verdict="PASS" if enough and all(gates.values()) else ("FAIL" if enough else "NOT_ENOUGH_PROSPECTIVE_EVIDENCE")

    summary={
        "version":VERSION,"protocol_id":PROTOCOL_ID,"status":"COMPLETE",
        "population":POPULATION,"ranker":RANKER,"top_k":TOP_K,
        "entry_policy":ENTRY_POLICY,"target_atr":TARGET_ATR,"stop_atr":STOP_ATR,
        "horizon_sessions":HORIZON_SESSIONS,
        "matured_observations":int(len(frame)),
        "matured_selected_observations":sm.get("n",0),
        "matured_selected_symbols":sm.get("symbols",0),
        "matured_complement_observations":cm.get("n",0),
        "selected_metrics":sm,
        "complement_metrics":cm,
        "nonoverlap_selected_metrics":snm,
        "same_day_uplift":uplift,
        "positive_month_fraction":positive_month_fraction,
        "frozen_gates":FROZEN_GATES,
        "gate_results":gates,
        "certification_verdict":verdict,
        "psve_candidate_001_unchanged":True,
        "mge_candidate_001_unchanged":True,
        "cqmi_candidate_001_unchanged":True,
        "historical_retuning_performed":False,
        "automatic_retraining":False,
        "production_capital_allocation_effect":False,
        "production_authority_effect":False,
    }
    _atomic_json(summary_path,summary)
    return summary


def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.30 prospective cross-sectional capital-priority shadow")
    p.add_argument("--project-root",required=True)
    p.add_argument("--action",choices=("freeze","record","update","evaluate"),default="record")
    return p


def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    root=Path(a.project_root).expanduser().resolve()
    cfg=CapitalPriorityShadowConfig(project_root=str(root))
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
