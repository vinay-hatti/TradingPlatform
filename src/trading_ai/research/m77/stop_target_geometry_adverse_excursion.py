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
from urllib.parse import unquote

import numpy as np
import pandas as pd

from trading_ai.research.m77.edge_discovery_lab import (
    engineer_ohlcv_features,
    read_daily_file,
)
from trading_ai.research.m77.positive_selection_edge_discovery import (
    PositiveSelectionConfig,
    load_development_authority,
)

VERSION = "M77.26.0-STOP-TARGET-GEOMETRY-ADVERSE-EXCURSION-EDGE-DISCOVERY-1.0"
DEVELOPMENT_END = pd.Timestamp("2017-12-31")
DRVE_REFERENCE_HORIZON = 20
ENTRY_POLICY = "NEXT_OPEN"
HORIZONS = (10, 15, 20, 30, 45, 60)
TARGET_ATR = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
STOP_ATR = (1.0, 1.5, 2.0, 2.5, 3.0)
WINNER_MAE_QUANTILES = (0.50, 0.75, 0.90, 0.95)


class GeometryError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeometryConfig:
    project_root: str
    daily_root: str = "research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization"
    prediction_path: str = "research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz"
    integrity_path: str = "research_data/m77_21_2_1/historical_price_integrity_lab/prediction_integrity_evidence.csv.gz"
    pit_candidate_path: str = "research_data/m77_22_3/point_in_time_long_candidate_veto/checkpoints/pit_long_candidate_authority.csv.gz"
    output_dir: str = "research_data/m77_26/stop_target_geometry_adverse_excursion_edge_discovery"
    workers: int = 6


def _resolve(root: Path, raw: str) -> Path:
    p=Path(raw).expanduser()
    return p if p.is_absolute() else root/p


def _json_default(v: Any) -> Any:
    if isinstance(v,(np.integer,)): return int(v)
    if isinstance(v,(np.floating,)): return None if not np.isfinite(v) else float(v)
    if isinstance(v,(pd.Timestamp,datetime)): return v.isoformat()
    if isinstance(v,Path): return str(v)
    raise TypeError(type(v).__name__)


def _atomic_json(path: Path,payload: Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True,default=_json_default))
    os.replace(tmp,path)


def _md(df:pd.DataFrame,n:int=30)->str:
    if df.empty:return "_No rows._"
    x=df.head(n); cols=[str(c) for c in x.columns]
    def f(v:Any)->str:
        if pd.isna(v):return ""
        if isinstance(v,(float,np.floating)):return f"{float(v):.6g}"
        return str(v).replace("|","\\|").replace("\n"," ")
    lines=["| "+" | ".join(cols)+" |","| "+" | ".join("---" for _ in cols)+" |"]
    for _,r in x.iterrows():lines.append("| "+" | ".join(f(r[c]) for c in x.columns)+" |")
    return "\n".join(lines)


def load_candidates(cfg:GeometryConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    pcfg=PositiveSelectionConfig(
        project_root=cfg.project_root,
        prediction_path=cfg.prediction_path,
        integrity_path=cfg.integrity_path,
        pit_candidate_path=cfg.pit_candidate_path,
    )
    panel,meta=load_development_authority(pcfg)
    c=panel[panel["horizon"]==DRVE_REFERENCE_HORIZON].copy()
    if c.empty:raise GeometryError("No Development Trade-Builder-ready + DRVE-pass candidate dates")
    cols=["symbol","as_of","probability_up","bearish_rank_pct"]
    for col in ("overall_score","score_overall","idi_trade_quality","score_options_suitability"):
        if col in c.columns:cols.append(col)
    c=c[[x for x in cols if x in c.columns]].drop_duplicates(["symbol","as_of"],keep="last")
    if (c["as_of"]>DEVELOPMENT_END).any():raise GeometryError("M77.26 refuses post-2017 candidate data")
    return c.sort_values(["symbol","as_of"]),meta


def _safe_symbol(path:Path)->str:
    suffix=".daily.csv.gz"
    stem=path.name[:-len(suffix)] if path.name.endswith(suffix) else path.stem
    try:return unquote(stem.replace("_","%"))
    except Exception:return stem


def _discover(root:Path)->dict[str,Path]:
    paths={}
    for p in sorted(root.rglob("*.daily.csv.gz")):
        sym=_safe_symbol(p)
        if sym not in paths:paths[sym]=p
    if not paths:raise GeometryError(f"No daily files under {root}")
    return paths


def _first_hit(mask:np.ndarray)->float:
    idx=np.flatnonzero(mask)
    return np.inf if len(idx)==0 else float(idx[0]+1)


def _barrier_result(highs:np.ndarray,lows:np.ndarray,entry:float,atr:float,target:float,stop:float)->tuple[float,float,float]:
    td=_first_hit(highs>=entry+target*atr)
    sd=_first_hit(lows<=entry-stop*atr)
    if np.isfinite(td) and np.isfinite(sd) and td==sd:return np.nan,td,sd
    if td<sd:return 1.0,td,sd
    if sd<td:return -1.0,td,sd
    return 0.0,td,sd


def _process_symbol(args:tuple[str,str,str])->tuple[str,list[dict[str,Any]],str|None]:
    symbol,raw_path,candidate_json=args
    try:
        cand=pd.read_json(StringIO(candidate_json),orient="records")
        cand["as_of"]=pd.to_datetime(cand["as_of"])
        df=read_daily_file(Path(raw_path),DEVELOPMENT_END.date().isoformat())
        if len(df)<320:return symbol,[],"INSUFFICIENT_HISTORY"
        df=engineer_ohlcv_features(df)
        by_date={pd.Timestamp(d).normalize():i for i,d in enumerate(df["as_of"])}
        rows=[]
        for _,cr in cand.iterrows():
            d=pd.Timestamp(cr["as_of"]).normalize();i=by_date.get(d)
            if i is None or i+1>=len(df):continue
            atr=float(df.iloc[i].get("atr_14",np.nan))
            if not math.isfinite(atr) or atr<=0:continue
            entry_idx=i+1;entry=float(df.iloc[entry_idx]["open"])
            if not math.isfinite(entry) or entry<=0:continue
            base=df.iloc[i]
            common={
                "symbol":symbol,"as_of":d,"entry_date":df.iloc[entry_idx]["as_of"],
                "entry_price":entry,"candidate_atr":atr,
                "probability_up":cr.get("probability_up"),"bearish_rank_pct":cr.get("bearish_rank_pct"),
                "overall_score":cr.get("score_overall",cr.get("overall_score")),
                "idi_trade_quality":cr.get("idi_trade_quality"),
                "score_options_suitability":cr.get("score_options_suitability"),
                "px_ret_5":base.get("px_ret_5"),"dist_sma_20":base.get("dist_sma_20"),
                "rsi_14":base.get("rsi_14"),"atr_pct_14":base.get("atr_pct_14"),
            }
            for h in HORIZONS:
                terminal=entry_idx+h
                if terminal>=len(df):continue
                # Entry day excluded from target/stop path ordering, consistent with M77.25.
                fut=df.iloc[entry_idx+1:terminal+1]
                highs=fut["high"].to_numpy(float);lows=fut["low"].to_numpy(float)
                terminal_close=float(df.iloc[terminal]["close"])
                ret=terminal_close/entry-1.0
                mfe=(float(np.nanmax(highs))-entry)/atr
                mae=(float(np.nanmin(lows))-entry)/atr
                row={**common,"horizon":h,"terminal_return":ret,"win":ret>0,
                     "mfe_atr":mfe,"mae_atr":mae}
                for target in TARGET_ATR:
                    for stop in STOP_ATR:
                        result,td,sd=_barrier_result(highs,lows,entry,atr,target,stop)
                        tag=f"t{str(target).replace('.','p')}_s{str(stop).replace('.','p')}"
                        row[f"barrier_{tag}"]=result
                        row[f"target_day_{tag}"]=td if np.isfinite(td) else np.nan
                        row[f"stop_day_{tag}"]=sd if np.isfinite(sd) else np.nan
                rows.append(row)
        if not rows:return symbol,[],"NO_CANDIDATE_DATES_MATCHED_RAW_SESSIONS"
        return symbol,rows,None
    except Exception as exc:
        return symbol,[],f"{type(exc).__name__}: {exc}"


def build_panel(cfg:GeometryConfig,candidates:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).resolve();daily=_resolve(root,cfg.daily_root)
    paths=_discover(daily);tasks=[];unmatched=[]
    for symbol,g in candidates.groupby("symbol",sort=False):
        symbol=str(symbol);p=paths.get(symbol)
        if p is None:unmatched.append(symbol);continue
        tasks.append((symbol,str(p),g.to_json(orient="records",date_format="iso")))
    if not tasks:raise GeometryError("No candidate symbols matched daily authority")
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
                sym,r,e=fut.result();rows.extend(r)
                if e:fails.append({"symbol":sym,"error":e})
    panel=pd.DataFrame(rows)
    if panel.empty:
        counts={}
        for x in fails:
            counts[x["error"]]=counts.get(x["error"],0)+1
        raise GeometryError(f"No geometry observations materialized; failures={sorted(counts.items(),key=lambda x:-x[1])[:10]}")
    panel["as_of"]=pd.to_datetime(panel["as_of"]);panel["entry_date"]=pd.to_datetime(panel["entry_date"])
    # Frozen contemporaneous bins used only for conditional diagnostics.
    panel["atr_pct_rank"]=panel.groupby(["as_of","horizon"])["atr_pct_14"].rank(pct=True,method="average")
    panel["quality_rank"]=panel.groupby(["as_of","horizon"])["overall_score"].rank(pct=True,method="average")
    diagnostics={
        "daily_files_discovered":len(paths),"candidate_symbols":int(candidates["symbol"].nunique()),
        "matched_candidate_symbols":len(tasks),"unmatched_candidate_symbols":len(unmatched),
        "unmatched_candidate_symbol_sample":sorted(unmatched)[:50],
    }
    return panel,pd.DataFrame(fails),diagnostics


def _resolved_metrics(g:pd.DataFrame,target:float,stop:float)->dict[str,Any]:
    tag=f"t{str(target).replace('.','p')}_s{str(stop).replace('.','p')}"
    vals=pd.to_numeric(g[f"barrier_{tag}"],errors="coerce")
    resolved=g[vals.isin([1.0,-1.0])].copy();rv=vals.loc[resolved.index]
    if resolved.empty:return {"resolved_n":0}
    wins=(rv==1.0)
    expectancy=np.where(wins,target/stop,-1.0)
    sym=pd.DataFrame({"symbol":resolved["symbol"].values,"r":expectancy}).groupby("symbol")["r"].mean()
    contrib=pd.DataFrame({"symbol":resolved["symbol"].values,"r":expectancy}).groupby("symbol")["r"].sum().abs().sort_values(ascending=False)
    denom=float(contrib.sum())
    td=pd.to_numeric(resolved[f"target_day_{tag}"],errors="coerce")
    sd=pd.to_numeric(resolved[f"stop_day_{tag}"],errors="coerce")
    return {
        "resolved_n":int(len(resolved)),"resolved_symbols":int(resolved["symbol"].nunique()),
        "resolved_fraction":float(len(resolved)/max(1,len(g))),
        "target_first_rate":float(wins.mean()),"expectancy_r":float(np.mean(expectancy)),
        "median_target_day":float(td[wins].median()) if wins.any() else np.nan,
        "median_stop_day":float(sd[~wins].median()) if (~wins).any() else np.nan,
        "equal_symbol_expectancy_r":float(sym.mean()) if len(sym) else np.nan,
        "positive_symbol_fraction":float((sym>0).mean()) if len(sym) else np.nan,
        "largest_symbol_abs_contribution_fraction":float(contrib.iloc[0]/denom) if denom>0 else np.nan,
        "top10_symbol_abs_contribution_fraction":float(contrib.head(10).sum()/denom) if denom>0 else np.nan,
    }


def geometry_evidence(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    rows=[];years=[];non=[]
    for h in HORIZONS:
        g=panel[panel["horizon"]==h]
        for target in TARGET_ATR:
            for stop in STOP_ATR:
                m=_resolved_metrics(g,target,stop)
                rows.append({"horizon":h,"target_atr":target,"stop_atr":stop,**m})
                for year,yg in g.groupby(g["as_of"].dt.year):
                    ym=_resolved_metrics(yg,target,stop)
                    years.append({"horizon":h,"target_atr":target,"stop_atr":stop,"year":int(year),**ym})
                # Non-overlap first candidate per symbol until horizon elapsed.
                keep=[]
                for _,sg in g.sort_values(["symbol","entry_date"]).groupby("symbol",sort=False):
                    last=None
                    for idx,r in sg.iterrows():
                        d=pd.Timestamp(r["entry_date"])
                        if last is None or (d-last).days>=math.ceil(h*7/5):
                            keep.append(idx);last=d
                nm=_resolved_metrics(g.loc[keep],target,stop) if keep else {"resolved_n":0}
                non.append({"horizon":h,"target_atr":target,"stop_atr":stop,**nm})
    return pd.DataFrame(rows),pd.DataFrame(years),pd.DataFrame(non)


def excursion_evidence(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    quant=[];loser=[];survival=[]
    for h in HORIZONS:
        g=panel[panel["horizon"]==h].copy()
        winners=g[g["terminal_return"]>0]
        losers=g[g["terminal_return"]<=0]
        # MAE is negative ATR; convert to adverse distance.
        w_adverse=(-pd.to_numeric(winners["mae_atr"],errors="coerce")).clip(lower=0).dropna()
        l_favorable=pd.to_numeric(losers["mfe_atr"],errors="coerce").clip(lower=0).dropna()
        for q in WINNER_MAE_QUANTILES:
            quant.append({"horizon":h,"quantile":q,"winner_adverse_excursion_atr":float(w_adverse.quantile(q)) if len(w_adverse) else np.nan,
                          "winner_n":int(len(w_adverse))})
        for q in (0.50,0.75,0.90,0.95):
            loser.append({"horizon":h,"quantile":q,"loser_favorable_excursion_atr":float(l_favorable.quantile(q)) if len(l_favorable) else np.nan,
                          "loser_n":int(len(l_favorable))})
        for stop in STOP_ATR:
            survival.append({
                "horizon":h,"stop_atr":stop,
                "eventual_winners":int(len(w_adverse)),
                "winner_fraction_surviving_stop":float((w_adverse<stop).mean()) if len(w_adverse) else np.nan,
                "winner_fraction_stopped":float((w_adverse>=stop).mean()) if len(w_adverse) else np.nan,
            })
    return pd.DataFrame(quant),pd.DataFrame(loser),pd.DataFrame(survival)


def conditional_evidence(panel:pd.DataFrame,geometry:pd.DataFrame)->pd.DataFrame:
    # Diagnostics only. Best aggregate geometry is frozen first by aggregate expectancy.
    if geometry.empty:return pd.DataFrame()
    best=geometry.sort_values(["expectancy_r","resolved_n"],ascending=[False,False]).iloc[0]
    h=int(best["horizon"]);target=float(best["target_atr"]);stop=float(best["stop_atr"])
    g=panel[panel["horizon"]==h].copy()
    states={
        "ATR_LOW":g["atr_pct_rank"]<=0.25,
        "ATR_HIGH":g["atr_pct_rank"]>=0.75,
        "QUALITY_LOW":g["quality_rank"]<=0.25,
        "QUALITY_HIGH":g["quality_rank"]>=0.75,
        "DRVE_RISK_LOWER":pd.to_numeric(g["bearish_rank_pct"],errors="coerce")>=0.50,
        "DRVE_RISK_HIGHER":pd.to_numeric(g["bearish_rank_pct"],errors="coerce")<=0.10,
        "MOM5_POSITIVE":pd.to_numeric(g["px_ret_5"],errors="coerce")>0,
        "MOM5_NONPOSITIVE":pd.to_numeric(g["px_ret_5"],errors="coerce")<=0,
        "ABOVE_SMA20":pd.to_numeric(g["dist_sma_20"],errors="coerce")>0,
        "BELOW_SMA20":pd.to_numeric(g["dist_sma_20"],errors="coerce")<=0,
    }
    rows=[]
    for name,mask in states.items():
        m=_resolved_metrics(g[mask.fillna(False)],target,stop)
        rows.append({"frozen_best_horizon":h,"frozen_best_target_atr":target,"frozen_best_stop_atr":stop,
                     "state":name,"candidate_n":int(mask.fillna(False).sum()),**m})
    return pd.DataFrame(rows)


def readiness(geometry:pd.DataFrame,years:pd.DataFrame,nonoverlap:pd.DataFrame)->pd.DataFrame:
    if geometry.empty:return pd.DataFrame()
    y=years.assign(pos=lambda x:x["expectancy_r"]>0).groupby(["horizon","target_atr","stop_atr"])["pos"].agg(["sum","count"]).reset_index()
    y["positive_year_fraction"]=y["sum"]/y["count"].replace(0,np.nan)
    n=nonoverlap[["horizon","target_atr","stop_atr","resolved_n","expectancy_r","equal_symbol_expectancy_r"]].rename(
        columns={"resolved_n":"nonoverlap_resolved_n","expectancy_r":"nonoverlap_expectancy_r",
                 "equal_symbol_expectancy_r":"nonoverlap_equal_symbol_expectancy_r"})
    out=geometry.merge(y[["horizon","target_atr","stop_atr","positive_year_fraction"]],on=["horizon","target_atr","stop_atr"],how="left").merge(
        n,on=["horizon","target_atr","stop_atr"],how="left")
    out["gate_resolved_n"]=out["resolved_n"]>=1000
    out["gate_symbols"]=out["resolved_symbols"]>=200
    out["gate_resolved_fraction"]=out["resolved_fraction"]>=0.50
    out["gate_expectancy"]=out["expectancy_r"]>=0.10
    out["gate_equal_symbol"]=out["equal_symbol_expectancy_r"]>0
    out["gate_positive_symbols"]=out["positive_symbol_fraction"]>=0.55
    out["gate_year_stability"]=out["positive_year_fraction"]>=0.70
    out["gate_nonoverlap"]=out["nonoverlap_expectancy_r"]>=0.05
    out["gate_concentration"]=out["top10_symbol_abs_contribution_fraction"]<=0.40
    gates=[c for c in out.columns if c.startswith("gate_")]
    out["development_ready"]=out[gates].all(axis=1)
    return out.sort_values(["development_ready","expectancy_r","nonoverlap_expectancy_r"],ascending=[False,False,False]).reset_index(drop=True)


def run_lab(cfg:GeometryConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve();outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    candidates,meta=load_candidates(cfg)
    panel,fails,diag=build_panel(cfg,candidates)
    geom,years,non=geometry_evidence(panel)
    wmae,lmfe,survival=excursion_evidence(panel)
    ready=readiness(geom,years,non)
    cond=conditional_evidence(panel,geom)

    panel.to_csv(outdir/"next_open_path_observation_panel.csv.gz",index=False,compression="gzip")
    geom.to_csv(outdir/"stop_target_geometry_evidence.csv",index=False)
    years.to_csv(outdir/"stop_target_geometry_year_evidence.csv",index=False)
    non.to_csv(outdir/"stop_target_geometry_nonoverlap_evidence.csv",index=False)
    wmae.to_csv(outdir/"eventual_winner_mae_quantiles.csv",index=False)
    lmfe.to_csv(outdir/"eventual_loser_mfe_quantiles.csv",index=False)
    survival.to_csv(outdir/"winner_stop_survival_evidence.csv",index=False)
    cond.to_csv(outdir/"conditional_geometry_diagnostics.csv",index=False)
    ready.to_csv(outdir/"stop_target_geometry_readiness.csv",index=False)
    fails.to_csv(outdir/"symbol_failures.csv",index=False)

    report=[
        "# M77.26 Stop/Target Geometry & Adverse-Excursion Edge Discovery","",
        "## Governance","",
        "- Development-only through 2017-12-31.",
        "- PIT Trade-Builder-ready LONG + certified DRVE PASS population.",
        "- NEXT_OPEN is the only entry policy studied.",
        "- 2018-2026 outcomes are not read.",
        "- M77.23 and M77.24.1 remain unchanged.",
        "- Same entry-day target/stop path ordering is excluded.","",
        "## Development-ready geometries","",_md(ready[ready["development_ready"]==True]),"",
        "## Highest aggregate expectancy geometries","",_md(ready.head(30)),"",
        "## Winner adverse-excursion quantiles","",_md(wmae),"",
        "## Winner stop survival","",_md(survival),"",
    ]
    (outdir/"STOP_TARGET_GEOMETRY_ADVERSE_EXCURSION_REPORT.md").write_text("\n".join(report))
    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31","consumed_2018_2026_rows_read":0,
        "entry_policy":ENTRY_POLICY,"candidate_dates":int(len(candidates)),
        "candidate_symbols":int(candidates["symbol"].nunique()),"path_observation_rows":int(len(panel)),
        "daily_authority_diagnostics":diag,"horizons":list(HORIZONS),
        "target_atr_grid":list(TARGET_ATR),"stop_atr_grid":list(STOP_ATR),
        "geometry_configurations":int(len(geom)),
        "development_ready_geometries":int(ready["development_ready"].sum()) if not ready.empty else 0,
        "symbol_failures":int(len(fails)),"conditional_diagnostic_rows":int(len(cond)),
        "m77_23_drv_modified":False,"m77_24_1_psve_modified":False,
        "production_authority_effect":False,"polygon_api_called":False,
        "next_step":"REVIEW DEVELOPMENT-ONLY MANAGEMENT GEOMETRY; DO NOT USE CONSUMED 2018-2026 TO RETUNE",
        "upstream_sha256":meta,
    }
    _atomic_json(outdir/"stop_target_geometry_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{"version":VERSION,"config":cfg.__dict__,"summary":summary})
    return summary


def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.26 Development-only stop/target geometry and adverse-excursion discovery")
    p.add_argument("--project-root",required=True)
    p.add_argument("--daily-root",default=GeometryConfig.daily_root)
    p.add_argument("--prediction-path",default=GeometryConfig.prediction_path)
    p.add_argument("--integrity-path",default=GeometryConfig.integrity_path)
    p.add_argument("--pit-candidate-path",default=GeometryConfig.pit_candidate_path)
    p.add_argument("--output-dir",default=GeometryConfig.output_dir)
    p.add_argument("--workers",type=int,default=max(1,min(6,(os.cpu_count() or 4)-1)))
    return p


def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    cfg=GeometryConfig(project_root=a.project_root,daily_root=a.daily_root,prediction_path=a.prediction_path,
                       integrity_path=a.integrity_path,pit_candidate_path=a.pit_candidate_path,
                       output_dir=a.output_dir,workers=a.workers)
    print(json.dumps(run_lab(cfg),indent=2,sort_keys=True,default=_json_default))
    return 0
