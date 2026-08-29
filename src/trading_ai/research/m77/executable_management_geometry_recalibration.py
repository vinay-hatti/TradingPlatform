from __future__ import annotations

import argparse
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trading_ai.research.m77.edge_discovery_lab import engineer_ohlcv_features, read_daily_file
from trading_ai.research.m77.stop_target_geometry_adverse_excursion import (
    DEVELOPMENT_END,
    DRVE_REFERENCE_HORIZON,
    HORIZONS,
    STOP_ATR,
    TARGET_ATR,
    _discover,
    _json_default,
    _md,
    _resolve,
    load_candidates,
)

VERSION = "M77.26.1-EXECUTABLE-MANAGEMENT-GEOMETRY-RECALIBRATION-1.0"
ENTRY_POLICY = "NEXT_OPEN"
AMBIGUITY_POLICY = "CONSERVATIVE_STOP"
TARGET_GAP_POLICY = "FILL_AT_TARGET"
STOP_GAP_POLICY = "FILL_AT_OPEN"
UNRESOLVED_POLICY = "EXIT_AT_HORIZON_CLOSE"


class ExecutableGeometryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutableGeometryConfig:
    project_root: str
    daily_root: str = "research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization"
    prediction_path: str = "research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz"
    integrity_path: str = "research_data/m77_21_2_1/historical_price_integrity_lab/prediction_integrity_evidence.csv.gz"
    pit_candidate_path: str = "research_data/m77_22_3/point_in_time_long_candidate_veto/checkpoints/pit_long_candidate_authority.csv.gz"
    output_dir: str = "research_data/m77_26_1/executable_management_geometry_recalibration"
    workers: int = 6


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True,default=_json_default))
    os.replace(tmp,path)


def _tag(target: float, stop: float) -> str:
    return f"t{str(target).replace('.','p')}_s{str(stop).replace('.','p')}"


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
