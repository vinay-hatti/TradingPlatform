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

VERSION="M77.29.1-RANKING-IDENTITY-INDEPENDENCE-CAPACITY-FORENSICS-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
PRIMARY_HORIZON=60
PRIMARY_TARGET_ATR=5.0
PRIMARY_STOP_ATR=3.0
TOP_K=(1,3,5,10)
PRIMARY_CAPACITY=10

class ForensicError(RuntimeError): pass

@dataclass(frozen=True)
class ForensicConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    capacity_evidence_path:str="research_data/m77_29/cross_sectional_ranking_opportunity_cost_edge_discovery/cross_sectional_capacity_evidence.csv"
    output_dir:str="research_data/m77_29_1/ranking_identity_independence_capacity_forensics"


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

def _md(df:pd.DataFrame,n:int=40)->str:
    if df.empty:return "_No rows._"
    x=df.head(n); cols=[str(c) for c in x.columns]
    def f(v):
        if pd.isna(v):return ""
        if isinstance(v,(float,np.floating)):return f"{float(v):.6g}"
        return str(v).replace("|","\\|").replace("\n"," ")
    lines=["| "+" | ".join(cols)+" |","| "+" | ".join("---" for _ in cols)+" |"]
    for _,r in x.iterrows():lines.append("| "+" | ".join(f(r[c]) for c in x.columns)+" |")
    return "\n".join(lines)

def load_panel(cfg:ForensicConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    p=_resolve(root,cfg.executable_panel_path)
    if not p.exists():raise ForensicError(f"Executable panel missing: {p}")
    df=pd.read_csv(p)
    df["as_of"]=pd.to_datetime(df["as_of"],errors="coerce")
    df["entry_date"]=pd.to_datetime(df["entry_date"],errors="coerce")
    df=df[
        (df["horizon"]==PRIMARY_HORIZON)
        &(df["target_atr"]==PRIMARY_TARGET_ATR)
        &(df["stop_atr"]==PRIMARY_STOP_ATR)
    ].copy()
    if df.empty:raise ForensicError("Frozen 60d/5ATR/3ATR cohort missing")
    if (df["as_of"]>DEVELOPMENT_END).any():raise ForensicError("M77.29.1 refuses post-2017 evidence")
    for c in ("probability_up","bearish_rank_pct","overall_score","idi_trade_quality","score_options_suitability","r_multiple","exit_day"):
        df[c]=pd.to_numeric(df.get(c),errors="coerce")
    df["calendar_year"]=df["as_of"].dt.year
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

def _rank_corr_rows(panel:pd.DataFrame)->pd.DataFrame:
    rows=[]
    for d,g in panel.groupby("as_of"):
        x=g[["probability_up","bearish_rank_pct","rank_probability_up","rank_drv_low_risk"]].dropna()
        if len(x)<3:continue
        pear=x["probability_up"].corr(x["bearish_rank_pct"],method="pearson")
        spear=x["probability_up"].corr(x["bearish_rank_pct"],method="spearman")
        rankcorr=x["rank_probability_up"].corr(x["rank_drv_low_risk"],method="pearson")
        order_prob=tuple(g.sort_values(["rank_probability_up","symbol"],ascending=[False,True])["symbol"])
        order_drv=tuple(g.sort_values(["rank_drv_low_risk","symbol"],ascending=[False,True])["symbol"])
        rows.append({
            "as_of":d,"n":len(x),"pearson_probability_vs_drv":pear,
            "spearman_probability_vs_drv":spear,"rank_corr":rankcorr,
            "exact_full_order_equal":order_prob==order_drv,
        })
    return pd.DataFrame(rows)

def _top_overlap(panel:pd.DataFrame)->pd.DataFrame:
    rows=[]
    for k in TOP_K:
        exact_dates=0; overlaps=[]; total_dates=0
        for d,g in panel.groupby("as_of"):
            a=list(g.sort_values(["rank_probability_up","symbol"],ascending=[False,True]).head(k)["symbol"])
            b=list(g.sort_values(["rank_drv_low_risk","symbol"],ascending=[False,True]).head(k)["symbol"])
            if not a or not b:continue
            total_dates+=1
            sa,sb=set(a),set(b)
            denom=max(1,min(len(sa),len(sb)))
            ov=len(sa&sb)/denom
            overlaps.append(ov)
            exact_dates+=int(a==b)
        rows.append({
            "top_k":k,"dates":total_dates,
            "mean_set_overlap_fraction":float(np.mean(overlaps)) if overlaps else np.nan,
            "exact_order_match_fraction":exact_dates/total_dates if total_dates else np.nan,
        })
    return pd.DataFrame(rows)

def _transformation_forensics(panel:pd.DataFrame)->dict[str,Any]:
    x=panel[["probability_up","bearish_rank_pct"]].dropna()
    if x.empty:return {}
    # Check common affine/inverse relationships.
    diff=x["bearish_rank_pct"]-x["probability_up"]
    invdiff=x["bearish_rank_pct"]-(1.0-x["probability_up"])
    a,b=np.polyfit(x["probability_up"],x["bearish_rank_pct"],1)
    pred=a*x["probability_up"]+b
    resid=x["bearish_rank_pct"]-pred
    return {
        "n":int(len(x)),
        "exact_equal_fraction":float(np.isclose(diff,0,rtol=0,atol=1e-12).mean()),
        "exact_one_minus_fraction":float(np.isclose(invdiff,0,rtol=0,atol=1e-12).mean()),
        "affine_slope":float(a),"affine_intercept":float(b),
        "affine_max_abs_residual":float(np.abs(resid).max()),
        "affine_mean_abs_residual":float(np.abs(resid).mean()),
        "probability_missing_fraction":float(panel["probability_up"].isna().mean()),
        "drv_missing_fraction":float(panel["bearish_rank_pct"].isna().mean()),
        "joint_missing_fraction":float((panel["probability_up"].isna()&panel["bearish_rank_pct"].isna()).mean()),
    }

def _winner(panel:pd.DataFrame,col:str)->pd.DataFrame:
    z=panel.dropna(subset=[col]).sort_values(["as_of",col,"symbol"],ascending=[True,False,True])
    return z.groupby("as_of",group_keys=False).head(1).copy()

def ensemble_independence(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    p=_winner(panel,"rank_probability_up").set_index("as_of")
    e=_winner(panel,"rank_ensemble_simple").set_index("as_of")
    dates=sorted(set(p.index)&set(e.index))
    rows=[];div=[]
    for d in dates:
        pr=p.loc[d];er=e.loc[d]
        same=str(pr["symbol"])==str(er["symbol"])
        rows.append({
            "as_of":d,"same_symbol":same,
            "probability_symbol":str(pr["symbol"]),
            "ensemble_symbol":str(er["symbol"]),
            "probability_r":float(pr["r_multiple"]),
            "ensemble_r":float(er["r_multiple"]),
            "ensemble_minus_probability_r":float(er["r_multiple"]-pr["r_multiple"]),
        })
        if not same:
            # Component rank deltas for divergence date.
            div.append({
                "as_of":d,
                "probability_symbol":str(pr["symbol"]),"ensemble_symbol":str(er["symbol"]),
                "probability_r":float(pr["r_multiple"]),"ensemble_r":float(er["r_multiple"]),
                "probability_rank_probability":float(pr["rank_probability_up"]),
                "ensemble_rank_probability":float(er["rank_probability_up"]),
                "probability_rank_drv":float(pr["rank_drv_low_risk"]),
                "ensemble_rank_drv":float(er["rank_drv_low_risk"]),
                "probability_rank_overall":float(pr["rank_overall_score"]),
                "ensemble_rank_overall":float(er["rank_overall_score"]),
                "probability_rank_idi":float(pr["rank_idi_trade_quality"]),
                "ensemble_rank_idi":float(er["rank_idi_trade_quality"]),
                "probability_rank_options":float(pr["rank_options_suitability"]),
                "ensemble_rank_options":float(er["rank_options_suitability"]),
            })
    return pd.DataFrame(rows),pd.DataFrame(div)

def _top3_probability(panel:pd.DataFrame)->pd.DataFrame:
    z=panel.sort_values(["as_of","rank_probability_up","symbol"],ascending=[True,False,True]).copy()
    z=z.groupby("as_of",group_keys=False).head(3).copy()
    z["selection_rank"]=z.groupby("as_of").cumcount()+1
    return z

def _capacity_split(selected:pd.DataFrame,max_concurrent:int=10)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    z=selected.sort_values(["as_of","selection_rank","symbol"]).copy()
    open_positions=[];accepted=[];skipped=[];events=[]
    for idx,row in z.iterrows():
        entry=pd.Timestamp(row["entry_date"])
        open_positions=[x for x in open_positions if x>entry]
        before=len(open_positions)
        if before>=max_concurrent:
            skipped.append(idx)
            events.append({"index":idx,"decision":"SKIP","concurrent_before":before})
            continue
        exit_day=float(row.get("exit_day",PRIMARY_HORIZON))
        exit_date=entry+pd.offsets.BDay(max(1,int(exit_day)))
        open_positions.append(pd.Timestamp(exit_date))
        accepted.append(idx)
        events.append({"index":idx,"decision":"ACCEPT","concurrent_before":before})
    return z.loc[accepted].copy(),z.loc[skipped].copy(),pd.DataFrame(events)

def _metrics(g:pd.DataFrame)->dict[str,Any]:
    if g.empty:return {"n":0}
    r=pd.to_numeric(g["r_multiple"],errors="coerce").dropna()
    if r.empty:return {"n":0}
    x=g.loc[r.index]
    gp=float(r[r>0].sum());gl=float(-r[r<0].sum())
    sym=x.assign(_r=r).groupby("symbol")["_r"].mean()
    return {
        "n":int(len(r)),"symbols":int(x["symbol"].nunique()),
        "mean_r":float(r.mean()),"median_r":float(r.median()),
        "win_rate":float((r>0).mean()),
        "profit_factor":float(gp/gl) if gl>0 else np.inf,
        "equal_symbol_mean_r":float(sym.mean()) if len(sym) else np.nan,
        "mean_exit_day":float(pd.to_numeric(x["exit_day"],errors="coerce").mean()),
    }

def capacity_forensics(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    top3=_top3_probability(panel)
    accepted,skipped,events=_capacity_split(top3,PRIMARY_CAPACITY)
    rows=[]
    for name,g in (("SELECTED_ALL",top3),("CAPACITY_ACCEPTED",accepted),("CAPACITY_SKIPPED",skipped)):
        m=_metrics(g)
        rows.append({"cohort":name,**m})
        for year,yg in g.groupby("calendar_year"):
            ym=_metrics(yg)
            rows.append({"cohort":f"{name}_YEAR_{int(year)}",**ym})
    return pd.DataFrame(rows),events

def run_lab(cfg:ForensicConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    panel,meta=load_panel(cfg)

    corr=_rank_corr_rows(panel)
    overlap=_top_overlap(panel)
    transform=_transformation_forensics(panel)
    ens,div=ensemble_independence(panel)
    cap,events=capacity_forensics(panel)

    corr.to_csv(outdir/"probability_drv_rank_correlation_by_date.csv",index=False)
    overlap.to_csv(outdir/"probability_drv_topk_overlap.csv",index=False)
    ens.to_csv(outdir/"ensemble_probability_winner_comparison.csv",index=False)
    div.to_csv(outdir/"ensemble_divergence_component_forensics.csv",index=False)
    cap.to_csv(outdir/"top3_capacity_cohort_forensics.csv",index=False)
    events.to_csv(outdir/"top3_capacity_decision_events.csv",index=False)
    _atomic_json(outdir/"probability_drv_transformation_forensics.json",transform)

    # Forensic conclusions are deterministic summaries, not new gates.
    rank_identity={
        "median_spearman":float(corr["spearman_probability_vs_drv"].median()) if not corr.empty else np.nan,
        "mean_rank_corr":float(corr["rank_corr"].mean()) if not corr.empty else np.nan,
        "exact_full_order_equal_fraction":float(corr["exact_full_order_equal"].mean()) if not corr.empty else np.nan,
        "topk_overlap":overlap.to_dict(orient="records"),
    }
    ensemble_summary={
        "dates":int(len(ens)),
        "same_winner_fraction":float(ens["same_symbol"].mean()) if not ens.empty else np.nan,
        "divergence_dates":int((~ens["same_symbol"]).sum()) if not ens.empty else 0,
        "mean_ensemble_minus_probability_r_on_divergence":float(
            ens.loc[~ens["same_symbol"],"ensemble_minus_probability_r"].mean()
        ) if not ens.empty and (~ens["same_symbol"]).any() else np.nan,
    }
    cap_rows={r["cohort"]:r for r in cap.to_dict(orient="records") if "_YEAR_" not in r["cohort"]}
    capacity_summary={
        "selected_all":cap_rows.get("SELECTED_ALL"),
        "accepted":cap_rows.get("CAPACITY_ACCEPTED"),
        "skipped":cap_rows.get("CAPACITY_SKIPPED"),
    }

    report=[
        "# M77.29.1 Ranking Identity, Independence & Capacity Forensics","",
        "## Probability vs DRVE identity","",
        "This section tests whether the two M77.29 ranking families are actually distinct rather than counting duplicate evidence.","",
        _md(corr.describe(include="all").reset_index()),"",
        "### Top-K overlap","",_md(overlap),"",
        "## Ensemble winner independence","",_md(ens.head(30)),"",
        "## Capacity cohorts","",_md(cap),"",
    ]
    (outdir/"RANKING_IDENTITY_INDEPENDENCE_CAPACITY_FORENSICS_REPORT.md").write_text("\n".join(report))

    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31","consumed_2018_2026_rows_read":0,
        "rank_identity":rank_identity,
        "transformation_forensics":transform,
        "ensemble_independence":ensemble_summary,
        "capacity_forensics":capacity_summary,
        "new_rankers_tested":0,"new_thresholds_tested":0,
        "m77_23_drv_modified":False,"m77_24_1_psve_modified":False,"m77_26_2_mge_modified":False,"m77_27_1_cqmi_modified":False,
        "production_authority_effect":False,"polygon_api_called":False,
        "next_step":"REVIEW FORENSIC IDENTITY/INDEPENDENCE/CAPACITY RESULTS BEFORE ANY NEW PROSPECTIVE CAPITAL-PRIORITY PROTOCOL",
        "upstream":meta,
    }
    _atomic_json(outdir/"ranking_identity_independence_capacity_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{"version":VERSION,"config":cfg.__dict__,"summary":summary})
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.29.1 ranking identity, independence and capacity forensics")
    p.add_argument("--project-root",required=True)
    p.add_argument("--executable-panel-path",default=ForensicConfig.executable_panel_path)
    p.add_argument("--capacity-evidence-path",default=ForensicConfig.capacity_evidence_path)
    p.add_argument("--output-dir",default=ForensicConfig.output_dir)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    cfg=ForensicConfig(project_root=a.project_root,executable_panel_path=a.executable_panel_path,
                       capacity_evidence_path=a.capacity_evidence_path,output_dir=a.output_dir)
    print(json.dumps(run_lab(cfg),indent=2,sort_keys=True,default=_json_default))
    return 0
