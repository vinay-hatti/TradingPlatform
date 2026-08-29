from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

VERSION="M77.29.0-CROSS-SECTIONAL-RANKING-OPPORTUNITY-COST-EDGE-DISCOVERY-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
PRIMARY_HORIZON=60
PRIMARY_TARGET_ATR=5.0
PRIMARY_STOP_ATR=3.0

TOP_K=(1,3,5,10)
MAX_CONCURRENT=(5,10,20)
RANKERS=(
    "PROBABILITY_UP",
    "DRVE_LOW_RISK",
    "OVERALL_SCORE",
    "IDI_TRADE_QUALITY",
    "OPTIONS_SUITABILITY",
    "ENSEMBLE_SIMPLE",
)

class RankingError(RuntimeError): pass

@dataclass(frozen=True)
class RankingConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    output_dir:str="research_data/m77_29/cross_sectional_ranking_opportunity_cost_edge_discovery"


def _resolve(root:Path,raw:str)->Path:
    p=Path(raw).expanduser()
    return p if p.is_absolute() else root/p

def _json_default(v:Any)->Any:
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.floating,)):return None if not np.isfinite(v) else float(v)
    if isinstance(v,(pd.Timestamp,datetime)):return v.isoformat()
    if isinstance(v,Path):return str(v)
    raise TypeError(type(v).__name__)

def _atomic_json(path:Path,payload:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True,default=_json_default))
    os.replace(tmp,path)

def _md(df:pd.DataFrame,n:int=30)->str:
    if df.empty:return "_No rows._"
    x=df.head(n); cols=[str(c) for c in x.columns]
    def f(v):
        if pd.isna(v):return ""
        if isinstance(v,(float,np.floating)):return f"{float(v):.6g}"
        return str(v).replace("|","\\|").replace("\n"," ")
    lines=["| "+" | ".join(cols)+" |","| "+" | ".join("---" for _ in cols)+" |"]
    for _,r in x.iterrows():lines.append("| "+" | ".join(f(r[c]) for c in x.columns)+" |")
    return "\n".join(lines)

def load_panel(cfg:RankingConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    p=_resolve(root,cfg.executable_panel_path)
    if not p.exists():raise RankingError(f"Executable Development panel missing: {p}")
    df=pd.read_csv(p)
    df["as_of"]=pd.to_datetime(df["as_of"],errors="coerce")
    df["entry_date"]=pd.to_datetime(df["entry_date"],errors="coerce")
    df=df[
        (df["horizon"]==PRIMARY_HORIZON)
        &(df["target_atr"]==PRIMARY_TARGET_ATR)
        &(df["stop_atr"]==PRIMARY_STOP_ATR)
    ].copy()
    if df.empty:raise RankingError("Frozen 60d/5ATR/3ATR executable cohort missing")
    if (df["as_of"]>DEVELOPMENT_END).any():raise RankingError("M77.29 refuses post-2017 evidence")
    for c in ("probability_up","bearish_rank_pct","overall_score","idi_trade_quality","score_options_suitability"):
        df[c]=pd.to_numeric(df.get(c),errors="coerce")
    df["calendar_year"]=df["as_of"].dt.year
    # PIT cross-sectional ranks per candidate date.
    df["rank_probability_up"]=df.groupby("as_of")["probability_up"].rank(pct=True,method="average")
    df["rank_drv_low_risk"]=df.groupby("as_of")["bearish_rank_pct"].rank(pct=True,method="average")
    df["rank_overall_score"]=df.groupby("as_of")["overall_score"].rank(pct=True,method="average")
    df["rank_idi_trade_quality"]=df.groupby("as_of")["idi_trade_quality"].rank(pct=True,method="average")
    df["rank_options_suitability"]=df.groupby("as_of")["score_options_suitability"].rank(pct=True,method="average")
    df["rank_ensemble_simple"]=df[[
        "rank_probability_up","rank_drv_low_risk","rank_overall_score",
        "rank_idi_trade_quality","rank_options_suitability"
    ]].mean(axis=1,skipna=True)
    return df,{
        "rows":int(len(df)),"symbols":int(df["symbol"].nunique()),
        "first_as_of":df["as_of"].min().date().isoformat(),
        "last_as_of":df["as_of"].max().date().isoformat(),
        "consumed_2018_2026_rows_read":0,
    }

def _score_col(ranker:str)->str:
    return {
        "PROBABILITY_UP":"rank_probability_up",
        "DRVE_LOW_RISK":"rank_drv_low_risk",
        "OVERALL_SCORE":"rank_overall_score",
        "IDI_TRADE_QUALITY":"rank_idi_trade_quality",
        "OPTIONS_SUITABILITY":"rank_options_suitability",
        "ENSEMBLE_SIMPLE":"rank_ensemble_simple",
    }[ranker]

def _metrics(g:pd.DataFrame)->dict[str,Any]:
    if g.empty:return {"n":0}
    r=pd.to_numeric(g["r_multiple"],errors="coerce").dropna()
    if r.empty:return {"n":0}
    x=g.loc[r.index]
    gp=float(r[r>0].sum());gl=float(-r[r<0].sum())
    sym=x.assign(_r=r).groupby("symbol")["_r"].mean()
    contrib=x.assign(_r=r).groupby("symbol")["_r"].sum().abs().sort_values(ascending=False)
    denom=float(contrib.sum())
    return {
        "n":int(len(r)),"symbols":int(x["symbol"].nunique()),
        "mean_r":float(r.mean()),"median_r":float(r.median()),
        "win_rate":float((r>0).mean()),
        "profit_factor":float(gp/gl) if gl>0 else np.inf,
        "equal_symbol_mean_r":float(sym.mean()) if len(sym) else np.nan,
        "positive_symbol_fraction":float((sym>0).mean()) if len(sym) else np.nan,
        "top10_abs_contribution_fraction":float(contrib.head(10).sum()/denom) if denom>0 else np.nan,
    }

def _select_topk(panel:pd.DataFrame,ranker:str,k:int)->pd.DataFrame:
    sc=_score_col(ranker)
    z=panel.dropna(subset=[sc]).copy()
    z=z.sort_values(["as_of",sc,"symbol"],ascending=[True,False,True])
    return z.groupby("as_of",group_keys=False).head(k).copy()

def _simulate_capacity(selected:pd.DataFrame,max_concurrent:int)->tuple[pd.DataFrame,dict[str,Any]]:
    # Deterministic equal-slot capacity model. One selected candidate consumes one
    # slot from NEXT_OPEN until realized exit_day. Candidates are considered in
    # as_of/rank order; no leverage or position resizing.
    if selected.empty:return selected,{"accepted":0,"skipped_capacity":0,"peak_concurrent":0}
    z=selected.sort_values(["as_of","selection_rank","symbol"]).copy()
    open_positions=[];accepted=[];skipped=0;peak=0
    for idx,row in z.iterrows():
        entry=pd.Timestamp(row["entry_date"])
        # release positions with exit date before/at new entry
        open_positions=[x for x in open_positions if x>entry]
        if len(open_positions)>=max_concurrent:
            skipped+=1
            continue
        exit_day=float(row.get("exit_day",PRIMARY_HORIZON))
        # approximate exit date using business-day offset from entry; enough for
        # deterministic opportunity-cost comparison, not execution certification.
        exit_date=entry+pd.offsets.BDay(max(1,int(exit_day)))
        open_positions.append(pd.Timestamp(exit_date))
        accepted.append(idx)
        peak=max(peak,len(open_positions))
    return z.loc[accepted].copy(),{
        "accepted":len(accepted),"skipped_capacity":skipped,"peak_concurrent":peak
    }

def ranking_evidence(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    baseline=_metrics(panel)
    rows=[];years=[];capacity_rows=[]
    for ranker in RANKERS:
        for k in TOP_K:
            selected=_select_topk(panel,ranker,k)
            selected["selection_rank"]=selected.groupby("as_of").cumcount()+1
            m=_metrics(selected)
            rows.append({
                "ranker":ranker,"top_k":k,**m,
                "baseline_mean_r":baseline.get("mean_r"),
                "baseline_profit_factor":baseline.get("profit_factor"),
                "mean_r_uplift":m.get("mean_r",np.nan)-baseline.get("mean_r",np.nan),
                "pf_uplift":m.get("profit_factor",np.nan)-baseline.get("profit_factor",np.nan),
                "candidate_capture_fraction":float(len(selected)/len(panel)),
                "skipped_candidate_fraction":float(1-len(selected)/len(panel)),
                "r_per_candidate_date":float(selected.groupby("as_of")["r_multiple"].sum().mean()) if not selected.empty else np.nan,
            })
            for year,yg in panel.groupby("calendar_year"):
                sy=_select_topk(yg,ranker,k)
                ym=_metrics(sy);yb=_metrics(yg)
                years.append({
                    "ranker":ranker,"top_k":k,"year":int(year),
                    "selected_n":ym.get("n",0),
                    "mean_r_uplift":ym.get("mean_r",np.nan)-yb.get("mean_r",np.nan),
                    "pf_uplift":ym.get("profit_factor",np.nan)-yb.get("profit_factor",np.nan),
                })
            for cap in MAX_CONCURRENT:
                accepted,diag=_simulate_capacity(selected,cap)
                cm=_metrics(accepted)
                capacity_rows.append({
                    "ranker":ranker,"top_k":k,"max_concurrent":cap,
                    **diag,**{f"capacity_{kk}":vv for kk,vv in cm.items()},
                    "capacity_capture_fraction":float(len(accepted)/len(selected)) if len(selected) else np.nan,
                    "opportunity_cost_skipped_r":float(
                        selected.loc[~selected.index.isin(accepted.index),"r_multiple"].sum()
                    ) if len(selected) else 0.0,
                })
    return pd.DataFrame(rows),pd.DataFrame(years),pd.DataFrame(capacity_rows)

def readiness(evidence:pd.DataFrame,years:pd.DataFrame,capacity:pd.DataFrame)->pd.DataFrame:
    y=years.assign(pos=lambda x:(x["mean_r_uplift"]>0)&(x["pf_uplift"]>0)).groupby(["ranker","top_k"])["pos"].agg(["sum","count"]).reset_index()
    y["positive_year_fraction"]=y["sum"]/y["count"].replace(0,np.nan)
    cap=capacity[capacity["max_concurrent"]==10][[
        "ranker","top_k","accepted","skipped_capacity","peak_concurrent",
        "capacity_mean_r","capacity_profit_factor","capacity_capture_fraction",
        "opportunity_cost_skipped_r"
    ]]
    out=evidence.merge(y[["ranker","top_k","positive_year_fraction"]],on=["ranker","top_k"],how="left").merge(cap,on=["ranker","top_k"],how="left")
    out["gate_n"]=out["n"]>=500
    out["gate_symbols"]=out["symbols"]>=150
    out["gate_mean_r"]=out["mean_r"]>=0.25
    out["gate_uplift"]=out["mean_r_uplift"]>=0.05
    out["gate_pf"]=out["profit_factor"]>=1.50
    out["gate_pf_uplift"]=out["pf_uplift"]>=0.10
    out["gate_equal_symbol"]=out["equal_symbol_mean_r"]>=0.20
    out["gate_positive_years"]=out["positive_year_fraction"]>=0.70
    out["gate_concentration"]=out["top10_abs_contribution_fraction"]<=0.25
    out["gate_capacity_mean_r"]=out["capacity_mean_r"]>=0.20
    out["gate_capacity_pf"]=out["capacity_profit_factor"]>=1.40
    gates=[c for c in out.columns if c.startswith("gate_")]
    out["development_ready_ranking"]=out[gates].all(axis=1)
    return out.sort_values(
        ["development_ready_ranking","capacity_mean_r","mean_r_uplift"],
        ascending=[False,False,False]
    ).reset_index(drop=True)

def run_lab(cfg:RankingConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    panel,meta=load_panel(cfg)
    evidence,years,capacity=ranking_evidence(panel)
    ready=readiness(evidence,years,capacity)

    evidence.to_csv(outdir/"cross_sectional_ranking_evidence.csv",index=False)
    years.to_csv(outdir/"cross_sectional_ranking_year_evidence.csv",index=False)
    capacity.to_csv(outdir/"cross_sectional_capacity_evidence.csv",index=False)
    ready.to_csv(outdir/"cross_sectional_ranking_readiness.csv",index=False)

    best=ready[ready["development_ready_ranking"]==True].head(1)
    report=[
        "# M77.29 Cross-Sectional Ranking & Opportunity-Cost Edge Discovery","",
        "## Frozen base","",
        "- Trade-Builder-ready LONG + DRVE PASS.",
        "- NEXT_OPEN / 5ATR target / 3ATR stop / 60 sessions.",
        "- Pre-2018 Development evidence only.",
        "- Finite-capital capacity is a deterministic slot simulation, not a production portfolio backtest.","",
        "## Development-ready ranking configurations","",_md(ready[ready["development_ready_ranking"]==True]),"",
        "## Highest-ranked configurations","",_md(ready.head(30)),"",
    ]
    (outdir/"CROSS_SECTIONAL_RANKING_OPPORTUNITY_COST_REPORT.md").write_text("\n".join(report))

    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31","consumed_2018_2026_rows_read":0,
        "frozen_management_geometry":{"entry":"NEXT_OPEN","horizon":60,"target_atr":5.0,"stop_atr":3.0},
        "rankers_tested":list(RANKERS),"top_k_tested":list(TOP_K),"max_concurrent_tested":list(MAX_CONCURRENT),
        "ranking_configurations":int(len(evidence)),
        "development_ready_rankings":int(ready["development_ready_ranking"].sum()),
        "primary_panel_rows":int(len(panel)),"primary_symbols":int(panel["symbol"].nunique()),
        "m77_23_drv_modified":False,"m77_24_1_psve_modified":False,"m77_26_2_mge_modified":False,"m77_27_1_cqmi_modified":False,
        "production_authority_effect":False,"polygon_api_called":False,
        "next_step":"REVIEW DEVELOPMENT-ONLY RANKING AND CAPACITY EVIDENCE; ANY SURVIVOR REQUIRES SEPARATE PROSPECTIVE GOVERNANCE",
        "upstream":meta,
    }
    if not best.empty:
        b=best.iloc[0]
        summary["highest_ranked_development_ready_configuration"]={
            "ranker":str(b["ranker"]),"top_k":int(b["top_k"]),
            "mean_r":float(b["mean_r"]),"mean_r_uplift":float(b["mean_r_uplift"]),
            "profit_factor":float(b["profit_factor"]),
            "capacity_mean_r":float(b["capacity_mean_r"]),
            "capacity_profit_factor":float(b["capacity_profit_factor"]),
            "positive_year_fraction":float(b["positive_year_fraction"]),
        }
    _atomic_json(outdir/"cross_sectional_ranking_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{"version":VERSION,"config":cfg.__dict__,"summary":summary})
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.29 Development-only cross-sectional ranking and opportunity-cost discovery")
    p.add_argument("--project-root",required=True)
    p.add_argument("--executable-panel-path",default=RankingConfig.executable_panel_path)
    p.add_argument("--output-dir",default=RankingConfig.output_dir)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    cfg=RankingConfig(project_root=a.project_root,executable_panel_path=a.executable_panel_path,output_dir=a.output_dir)
    print(json.dumps(run_lab(cfg),indent=2,sort_keys=True,default=_json_default))
    return 0
