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

VERSION="M77.29.3-ENSEMBLE-PAYOFF-DISTRIBUTION-COMPONENT-CAUSALITY-FORENSICS-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
PRIMARY_HORIZON=60
PRIMARY_TARGET_ATR=5.0
PRIMARY_STOP_ATR=3.0
COMPONENTS=(
    "rank_probability_up",
    "rank_drv_low_risk",
    "rank_overall_score",
    "rank_idi_trade_quality",
    "rank_options_suitability",
)

class EnsembleCausalityError(RuntimeError): pass

@dataclass(frozen=True)
class EnsembleCausalityConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    output_dir:str="research_data/m77_29_3/ensemble_payoff_distribution_component_causality_forensics"


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

def load_panel(cfg:EnsembleCausalityConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    p=_resolve(root,cfg.executable_panel_path)
    if not p.exists():
        raise EnsembleCausalityError(f"Executable Development panel missing: {p}")
    df=pd.read_csv(p)
    df["as_of"]=pd.to_datetime(df["as_of"],errors="coerce")
    df["entry_date"]=pd.to_datetime(df["entry_date"],errors="coerce")
    df=df[
        (df["horizon"]==PRIMARY_HORIZON)
        &(df["target_atr"]==PRIMARY_TARGET_ATR)
        &(df["stop_atr"]==PRIMARY_STOP_ATR)
    ].copy()
    if df.empty:
        raise EnsembleCausalityError("Frozen 60d/5ATR/3ATR cohort missing")
    if (df["as_of"]>DEVELOPMENT_END).any():
        raise EnsembleCausalityError("M77.29.3 refuses post-2017 evidence")
    for c in ("probability_up","bearish_rank_pct","overall_score","idi_trade_quality","score_options_suitability","r_multiple","exit_day"):
        df[c]=pd.to_numeric(df.get(c),errors="coerce")
    df["calendar_year"]=df["as_of"].dt.year
    df["rank_probability_up"]=df.groupby("as_of")["probability_up"].rank(pct=True,method="average")
    df["rank_drv_low_risk"]=df.groupby("as_of")["bearish_rank_pct"].rank(pct=True,method="average")
    df["rank_overall_score"]=df.groupby("as_of")["overall_score"].rank(pct=True,method="average")
    df["rank_idi_trade_quality"]=df.groupby("as_of")["idi_trade_quality"].rank(pct=True,method="average")
    df["rank_options_suitability"]=df.groupby("as_of")["score_options_suitability"].rank(pct=True,method="average")
    df["rank_ensemble_simple"]=df[list(COMPONENTS)].mean(axis=1,skipna=True)
    return df,{
        "rows":int(len(df)),"symbols":int(df["symbol"].nunique()),
        "first_as_of":df["as_of"].min().date().isoformat(),
        "last_as_of":df["as_of"].max().date().isoformat(),
        "consumed_2018_2026_rows_read":0,
    }

def _winner(panel:pd.DataFrame,col:str)->pd.DataFrame:
    z=panel.dropna(subset=[col]).sort_values(["as_of",col,"symbol"],ascending=[True,False,True])
    return z.groupby("as_of",group_keys=False).head(1).copy()

def _metrics_from_diff(diff:pd.Series)->dict[str,Any]:
    d=pd.to_numeric(diff,errors="coerce").dropna()
    if d.empty:return {"n":0}
    wins=d[d>0]; losses=d[d<0]
    return {
        "n":int(len(d)),
        "mean":float(d.mean()),
        "median":float(d.median()),
        "p10":float(d.quantile(.10)),
        "p25":float(d.quantile(.25)),
        "p50":float(d.quantile(.50)),
        "p75":float(d.quantile(.75)),
        "p90":float(d.quantile(.90)),
        "positive_fraction":float((d>0).mean()),
        "negative_fraction":float((d<0).mean()),
        "mean_positive":float(wins.mean()) if len(wins) else np.nan,
        "median_positive":float(wins.median()) if len(wins) else np.nan,
        "mean_negative":float(losses.mean()) if len(losses) else np.nan,
        "median_negative":float(losses.median()) if len(losses) else np.nan,
    }

def _tail_contribution(diff:pd.Series)->pd.DataFrame:
    d=pd.to_numeric(diff,errors="coerce").dropna()
    pos=d[d>0].sort_values(ascending=False)
    total=float(pos.sum())
    rows=[]
    for frac in (0.01,0.05,0.10,0.20):
        if pos.empty:
            n=0; contrib=np.nan
        else:
            n=max(1,int(math.ceil(len(pos)*frac)))
            contrib=float(pos.head(n).sum()/total) if total>0 else np.nan
        rows.append({
            "top_positive_fraction":frac,
            "positive_observation_count":int(len(pos)),
            "included_count":int(n),
            "share_of_total_positive_advantage":contrib,
        })
    return pd.DataFrame(rows)

def divergence_distribution(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    prob=_winner(panel,"rank_probability_up").set_index("as_of")
    ens=_winner(panel,"rank_ensemble_simple").set_index("as_of")
    rows=[]
    for d in sorted(set(prob.index)&set(ens.index)):
        p=prob.loc[d];e=ens.loc[d]
        same=str(p["symbol"])==str(e["symbol"])
        rows.append({
            "as_of":d,"same_symbol":same,
            "probability_symbol":str(p["symbol"]),"ensemble_symbol":str(e["symbol"]),
            "probability_r":float(p["r_multiple"]),"ensemble_r":float(e["r_multiple"]),
            "ensemble_minus_probability_r":float(e["r_multiple"]-p["r_multiple"]),
            "calendar_year":int(pd.Timestamp(d).year),
        })
    cmp=pd.DataFrame(rows)
    div=cmp[cmp["same_symbol"]==False].copy()
    tail=_tail_contribution(div["ensemble_minus_probability_r"] if "ensemble_minus_probability_r" in div.columns else pd.Series(dtype=float))
    return cmp,div,tail

def component_causality(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    full=_winner(panel,"rank_ensemble_simple").set_index("as_of")
    prob=_winner(panel,"rank_probability_up").set_index("as_of")
    rows=[];year_rows=[]
    for omitted in COMPONENTS:
        remaining=[c for c in COMPONENTS if c!=omitted]
        z=panel.copy()
        col=f"loo_{omitted}"
        z[col]=z[remaining].mean(axis=1,skipna=True)
        w=_winner(z,col).set_index("as_of")
        dates=sorted(set(full.index)&set(prob.index)&set(w.index))
        diffs=[];same_full=[];same_prob=[]
        for d in dates:
            f=full.loc[d];p=prob.loc[d];q=w.loc[d]
            diffs.append(float(q["r_multiple"]-f["r_multiple"]))
            same_full.append(str(q["symbol"])==str(f["symbol"]))
            same_prob.append(str(q["symbol"])==str(p["symbol"]))
            year_rows.append({
                "omitted_component":omitted,"year":int(pd.Timestamp(d).year),
                "same_as_full":str(q["symbol"])==str(f["symbol"]),
                "same_as_probability":str(q["symbol"])==str(p["symbol"]),
                "loo_minus_full_r":float(q["r_multiple"]-f["r_multiple"]),
            })
        rows.append({
            "omitted_component":omitted,
            "dates":len(dates),
            "same_as_full_ensemble_fraction":float(np.mean(same_full)) if same_full else np.nan,
            "same_as_probability_fraction":float(np.mean(same_prob)) if same_prob else np.nan,
            "mean_loo_minus_full_ensemble_r":float(np.mean(diffs)) if diffs else np.nan,
            "median_loo_minus_full_ensemble_r":float(np.median(diffs)) if diffs else np.nan,
            "full_ensemble_dependence_fraction":float(1-np.mean(same_full)) if same_full else np.nan,
        })
    yr=pd.DataFrame(year_rows)
    if not yr.empty:
        yr=yr.groupby(["omitted_component","year"]).agg(
            dates=("year","size"),
            same_as_full_fraction=("same_as_full","mean"),
            same_as_probability_fraction=("same_as_probability","mean"),
            mean_loo_minus_full_r=("loo_minus_full_r","mean"),
        ).reset_index()
    return pd.DataFrame(rows),yr

def divergence_component_deltas(panel:pd.DataFrame)->pd.DataFrame:
    prob=_winner(panel,"rank_probability_up").set_index("as_of")
    ens=_winner(panel,"rank_ensemble_simple").set_index("as_of")
    rows=[]
    for d in sorted(set(prob.index)&set(ens.index)):
        p=prob.loc[d];e=ens.loc[d]
        if str(p["symbol"])==str(e["symbol"]):
            continue
        rdiff=float(e["r_multiple"]-p["r_multiple"])
        for c in COMPONENTS:
            rows.append({
                "as_of":d,"component":c,
                "ensemble_minus_probability_component_rank":float(e[c]-p[c]),
                "ensemble_minus_probability_r":rdiff,
                "ensemble_wins":rdiff>0,
            })
    return pd.DataFrame(rows)

def component_outcome_attribution(deltas:pd.DataFrame)->pd.DataFrame:
    rows=[]
    if deltas.empty:return pd.DataFrame()
    for c,g in deltas.groupby("component"):
        x=pd.to_numeric(g["ensemble_minus_probability_component_rank"],errors="coerce")
        y=pd.to_numeric(g["ensemble_minus_probability_r"],errors="coerce")
        mask=x.notna()&y.notna()
        xx=x[mask];yy=y[mask]
        rows.append({
            "component":c,"n":int(mask.sum()),
            "mean_rank_advantage_when_ensemble_wins":float(xx[yy>0].mean()) if (yy>0).any() else np.nan,
            "mean_rank_advantage_when_ensemble_loses":float(xx[yy<0].mean()) if (yy<0).any() else np.nan,
            "rank_delta_vs_r_pearson":float(xx.corr(yy,method="pearson")) if len(xx)>=3 else np.nan,
            "rank_delta_vs_r_spearman":float(xx.corr(yy,method="spearman")) if len(xx)>=3 else np.nan,
        })
    return pd.DataFrame(rows)

def run_lab(cfg:EnsembleCausalityConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    panel,meta=load_panel(cfg)

    cmp,div,tail=divergence_distribution(panel)
    loo,loo_year=component_causality(panel)
    deltas=divergence_component_deltas(panel)
    comp_attr=component_outcome_attribution(deltas)

    cmp.to_csv(outdir/"ensemble_probability_all_dates.csv",index=False)
    div.to_csv(outdir/"ensemble_probability_divergence_dates.csv",index=False)
    tail.to_csv(outdir/"ensemble_positive_tail_contribution.csv",index=False)
    loo.to_csv(outdir/"ensemble_leave_one_component_out_causality.csv",index=False)
    loo_year.to_csv(outdir/"ensemble_leave_one_component_out_year_evidence.csv",index=False)
    deltas.to_csv(outdir/"ensemble_divergence_component_rank_deltas.csv",index=False)
    comp_attr.to_csv(outdir/"ensemble_component_outcome_attribution.csv",index=False)

    dist=_metrics_from_diff(div["ensemble_minus_probability_r"]) if not div.empty else {"n":0}
    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31","consumed_2018_2026_rows_read":0,
        "new_rankers_tested":0,"new_thresholds_tested":0,"ensemble_weights_retuned":False,
        "divergence_dates":int(len(div)),
        "same_winner_fraction":float(cmp["same_symbol"].mean()) if len(cmp) else np.nan,
        "divergence_payoff_distribution":dist,
        "positive_tail_contribution":tail.to_dict(orient="records"),
        "leave_one_component_out":loo.to_dict(orient="records"),
        "component_outcome_attribution":comp_attr.to_dict(orient="records"),
        "m77_23_drv_modified":False,"m77_24_1_psve_modified":False,"m77_26_2_mge_modified":False,"m77_27_1_cqmi_modified":False,
        "production_authority_effect":False,"polygon_api_called":False,
        "next_step":"REVIEW WHETHER ENSEMBLE ADVANTAGE IS BROAD OR TAIL-CONCENTRATED AND WHETHER ONE FROZEN COMPONENT DOMINATES WINNER CAUSALITY BEFORE ANY PROSPECTIVE ENSEMBLE PROTOCOL",
        "upstream":meta,
    }

    report=[
        "# M77.29.3 Ensemble Payoff Distribution & Component Causality Forensics","",
        "## Divergence payoff distribution","",_md(pd.DataFrame([dist])),"",
        "## Positive-tail contribution","",_md(tail),"",
        "## Leave-one-component-out causality","",_md(loo),"",
        "## Component outcome attribution","",_md(comp_attr),"",
    ]
    (outdir/"ENSEMBLE_PAYOFF_DISTRIBUTION_COMPONENT_CAUSALITY_REPORT.md").write_text("\n".join(report))
    _atomic_json(outdir/"ensemble_payoff_distribution_component_causality_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{"version":VERSION,"config":cfg.__dict__,"summary":summary})
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.29.3 ensemble payoff distribution and component causality forensics")
    p.add_argument("--project-root",required=True)
    p.add_argument("--executable-panel-path",default=EnsembleCausalityConfig.executable_panel_path)
    p.add_argument("--output-dir",default=EnsembleCausalityConfig.output_dir)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    cfg=EnsembleCausalityConfig(project_root=a.project_root,executable_panel_path=a.executable_panel_path,output_dir=a.output_dir)
    print(json.dumps(run_lab(cfg),indent=2,sort_keys=True,default=_json_default))
    return 0
