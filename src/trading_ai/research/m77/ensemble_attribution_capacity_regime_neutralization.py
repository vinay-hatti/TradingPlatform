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

VERSION="M77.29.2-ENSEMBLE-ATTRIBUTION-CAPACITY-REGIME-NEUTRALIZATION-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
PRIMARY_HORIZON=60
PRIMARY_TARGET_ATR=5.0
PRIMARY_STOP_ATR=3.0
PRIMARY_CAPACITY=10
COMPONENTS=(
    "rank_probability_up",
    "rank_drv_low_risk",
    "rank_overall_score",
    "rank_idi_trade_quality",
    "rank_options_suitability",
)

class NeutralizationError(RuntimeError): pass

@dataclass(frozen=True)
class NeutralizationConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    regime_calendar_path:str="research_data/m77_28/regime_conditioned_edge_stability_discovery/point_in_time_regime_calendar.csv"
    output_dir:str="research_data/m77_29_2/ensemble_attribution_capacity_regime_neutralization"


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

def load_inputs(cfg:NeutralizationConfig)->tuple[pd.DataFrame,pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    ep=_resolve(root,cfg.executable_panel_path)
    rp=_resolve(root,cfg.regime_calendar_path)
    for p in (ep,rp):
        if not p.exists():raise NeutralizationError(f"Required Development evidence missing: {p}")
    e=pd.read_csv(ep)
    e["as_of"]=pd.to_datetime(e["as_of"],errors="coerce")
    e["entry_date"]=pd.to_datetime(e["entry_date"],errors="coerce")
    e=e[
        (e["horizon"]==PRIMARY_HORIZON)
        &(e["target_atr"]==PRIMARY_TARGET_ATR)
        &(e["stop_atr"]==PRIMARY_STOP_ATR)
    ].copy()
    if e.empty:raise NeutralizationError("Frozen 60d/5ATR/3ATR cohort missing")
    if (e["as_of"]>DEVELOPMENT_END).any():raise NeutralizationError("M77.29.2 refuses post-2017 executable evidence")
    for c in ("probability_up","bearish_rank_pct","overall_score","idi_trade_quality","score_options_suitability","r_multiple","exit_day"):
        e[c]=pd.to_numeric(e.get(c),errors="coerce")
    e["calendar_year"]=e["as_of"].dt.year
    e["calendar_month"]=e["as_of"].dt.to_period("M").astype(str)

    e["rank_probability_up"]=e.groupby("as_of")["probability_up"].rank(pct=True,method="average")
    e["rank_drv_low_risk"]=e.groupby("as_of")["bearish_rank_pct"].rank(pct=True,method="average")
    e["rank_overall_score"]=e.groupby("as_of")["overall_score"].rank(pct=True,method="average")
    e["rank_idi_trade_quality"]=e.groupby("as_of")["idi_trade_quality"].rank(pct=True,method="average")
    e["rank_options_suitability"]=e.groupby("as_of")["score_options_suitability"].rank(pct=True,method="average")
    e["rank_ensemble_simple"]=e[list(COMPONENTS)].mean(axis=1,skipna=True)

    r=pd.read_csv(rp)
    date_col=next((c for c in ("as_of","market_date","date") if c in r.columns),None)
    if date_col is None:raise NeutralizationError("Regime calendar has no supported date column")
    r["as_of"]=pd.to_datetime(r[date_col],errors="coerce")
    if (r["as_of"]>DEVELOPMENT_END).any():raise NeutralizationError("M77.29.2 refuses post-2017 regime evidence")

    return e,r,{
        "rows":int(len(e)),"symbols":int(e["symbol"].nunique()),
        "first_as_of":e["as_of"].min().date().isoformat(),
        "last_as_of":e["as_of"].max().date().isoformat(),
        "regime_rows":int(len(r)),
        "consumed_2018_2026_rows_read":0,
    }

def _winner(panel:pd.DataFrame,col:str)->pd.DataFrame:
    z=panel.dropna(subset=[col]).sort_values(["as_of",col,"symbol"],ascending=[True,False,True])
    return z.groupby("as_of",group_keys=False).head(1).copy()

def _metrics(g:pd.DataFrame)->dict[str,Any]:
    if g.empty:return {"n":0}
    r=pd.to_numeric(g["r_multiple"],errors="coerce").dropna()
    if r.empty:return {"n":0}
    x=g.loc[r.index]
    gp=float(r[r>0].sum());gl=float(-r[r<0].sum())
    return {
        "n":int(len(r)),
        "mean_r":float(r.mean()),
        "median_r":float(r.median()),
        "win_rate":float((r>0).mean()),
        "profit_factor":float(gp/gl) if gl>0 else np.inf,
        "mean_exit_day":float(pd.to_numeric(x["exit_day"],errors="coerce").mean()),
        "symbols":int(x["symbol"].nunique()),
    }

def ensemble_attribution(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    prob=_winner(panel,"rank_probability_up").set_index("as_of")
    ens=_winner(panel,"rank_ensemble_simple").set_index("as_of")
    dates=sorted(set(prob.index)&set(ens.index))
    comparisons=[];component_rows=[];loo_rows=[]
    for d in dates:
        p=prob.loc[d]; e=ens.loc[d]
        same=str(p["symbol"])==str(e["symbol"])
        comparisons.append({
            "as_of":d,"same_symbol":same,
            "probability_symbol":str(p["symbol"]),"ensemble_symbol":str(e["symbol"]),
            "probability_r":float(p["r_multiple"]),"ensemble_r":float(e["r_multiple"]),
            "ensemble_minus_probability_r":float(e["r_multiple"]-p["r_multiple"]),
        })
        if same:continue
        for c in COMPONENTS:
            component_rows.append({
                "as_of":d,"component":c,
                "probability_symbol":str(p["symbol"]),"ensemble_symbol":str(e["symbol"]),
                "probability_component_rank":float(p[c]) if pd.notna(p[c]) else np.nan,
                "ensemble_component_rank":float(e[c]) if pd.notna(e[c]) else np.nan,
                "ensemble_minus_probability_component_rank":float(e[c]-p[c]) if pd.notna(e[c]) and pd.notna(p[c]) else np.nan,
                "ensemble_minus_probability_r":float(e["r_multiple"]-p["r_multiple"]),
            })
    # Leave-one-component-out attribution, fixed equal weighting of remaining frozen components.
    for omitted in COMPONENTS:
        remaining=[c for c in COMPONENTS if c!=omitted]
        z=panel.copy()
        col=f"loo_{omitted}"
        z[col]=z[remaining].mean(axis=1,skipna=True)
        w=_winner(z,col).set_index("as_of")
        overlap=sorted(set(w.index)&set(ens.index)&set(prob.index))
        if not overlap:continue
        same_ens=[];same_prob=[];r_diff=[]
        for d in overlap:
            ww=w.loc[d]; ee=ens.loc[d]; pp=prob.loc[d]
            same_ens.append(str(ww["symbol"])==str(ee["symbol"]))
            same_prob.append(str(ww["symbol"])==str(pp["symbol"]))
            r_diff.append(float(ww["r_multiple"]-ee["r_multiple"]))
        loo_rows.append({
            "omitted_component":omitted,"dates":len(overlap),
            "same_as_full_ensemble_fraction":float(np.mean(same_ens)),
            "same_as_probability_fraction":float(np.mean(same_prob)),
            "mean_loo_minus_full_ensemble_r":float(np.mean(r_diff)),
        })
    return pd.DataFrame(comparisons),pd.DataFrame(component_rows),pd.DataFrame(loo_rows)

def _top3_probability(panel:pd.DataFrame)->pd.DataFrame:
    z=panel.sort_values(["as_of","rank_probability_up","symbol"],ascending=[True,False,True]).copy()
    z=z.groupby("as_of",group_keys=False).head(3).copy()
    z["selection_rank"]=z.groupby("as_of").cumcount()+1
    return z

def _capacity_split(selected:pd.DataFrame,max_concurrent:int=10)->tuple[pd.DataFrame,pd.DataFrame]:
    z=selected.sort_values(["as_of","selection_rank","symbol"]).copy()
    open_positions=[];accepted=[];skipped=[]
    for idx,row in z.iterrows():
        entry=pd.Timestamp(row["entry_date"])
        open_positions=[x for x in open_positions if x>entry]
        if len(open_positions)>=max_concurrent:
            skipped.append(idx);continue
        exit_day=float(row.get("exit_day",PRIMARY_HORIZON))
        exit_date=entry+pd.offsets.BDay(max(1,int(exit_day)))
        open_positions.append(pd.Timestamp(exit_date))
        accepted.append(idx)
    return z.loc[accepted].copy(),z.loc[skipped].copy()

def _discover_regime_columns(regime:pd.DataFrame)->list[str]:
    from pandas.api.types import is_object_dtype, is_string_dtype

    def _is_state_dtype(series:pd.Series)->bool:
        dtype=series.dtype
        return bool(
            is_object_dtype(dtype)
            or is_string_dtype(dtype)
            or isinstance(dtype, pd.CategoricalDtype)
        )

    preferred=[]
    for c in regime.columns:
        uc=str(c).upper()
        if c=="as_of":
            continue
        if any(token in uc for token in ("VOLAT","TREND","MOMENTUM","PROBABILITY_LEVEL","COMPOSITE")):
            if _is_state_dtype(regime[c]):
                preferred.append(c)

    # Fall back to low-cardinality textual/category state columns, excluding metadata.
    if not preferred:
        for c in regime.columns:
            if c=="as_of":
                continue
            if _is_state_dtype(regime[c]) and regime[c].nunique(dropna=True)<=12:
                preferred.append(c)
    return sorted(set(preferred))

def _weighted_gap(df:pd.DataFrame,group_cols:list[str])->dict[str,Any]:
    # Standardize accepted/skipped comparison to equal stratum weights among strata
    # containing both cohorts. This removes differences in regime/calendar mixture.
    rows=[]
    for keys,g in df.groupby(group_cols,dropna=False):
        a=g[g["capacity_cohort"]=="ACCEPTED"]
        s=g[g["capacity_cohort"]=="SKIPPED"]
        if a.empty or s.empty:continue
        rows.append({
            "keys":keys if isinstance(keys,tuple) else (keys,),
            "accepted_n":len(a),"skipped_n":len(s),
            "accepted_mean_r":float(a["r_multiple"].mean()),
            "skipped_mean_r":float(s["r_multiple"].mean()),
            "gap":float(a["r_multiple"].mean()-s["r_multiple"].mean()),
        })
    if not rows:return {"strata":0}
    # Equal-stratum and harmonic-size weighted summaries.
    gaps=np.array([r["gap"] for r in rows],float)
    weights=np.array([2*r["accepted_n"]*r["skipped_n"]/(r["accepted_n"]+r["skipped_n"]) for r in rows],float)
    return {
        "strata":len(rows),
        "equal_stratum_mean_gap_r":float(gaps.mean()),
        "matched_size_weighted_gap_r":float(np.average(gaps,weights=weights)) if weights.sum()>0 else np.nan,
        "positive_gap_fraction":float((gaps>0).mean()),
        "total_matched_effective_weight":float(weights.sum()),
    }

def capacity_neutralization(panel:pd.DataFrame,regime:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    top3=_top3_probability(panel)
    acc,skp=_capacity_split(top3,PRIMARY_CAPACITY)
    acc=acc.copy();skp=skp.copy()
    acc["capacity_cohort"]="ACCEPTED";skp["capacity_cohort"]="SKIPPED"
    both=pd.concat([acc,skp],ignore_index=True)
    regime_cols=_discover_regime_columns(regime)
    merge_cols=["as_of"]+regime_cols
    both=both.merge(regime[merge_cols].drop_duplicates("as_of"),on="as_of",how="left",validate="many_to_one")
    both["calendar_year"]=both["as_of"].dt.year
    both["calendar_month"]=both["as_of"].dt.to_period("M").astype(str)

    summaries=[]
    for name,cols in [
        ("YEAR",["calendar_year"]),
        ("MONTH",["calendar_month"]),
        ("SELECTION_RANK",["selection_rank"]),
    ]:
        d=_weighted_gap(both,cols);summaries.append({"neutralization":name,**d})
    for c in regime_cols:
        d=_weighted_gap(both,[c]);summaries.append({"neutralization":f"REGIME::{c}",**d})
    if regime_cols:
        # Combined coarse neutralization: year + all available structural state cols.
        d=_weighted_gap(both,["calendar_year"]+regime_cols)
        summaries.append({"neutralization":"YEAR_PLUS_ALL_REGIMES",**d})
    return pd.DataFrame(summaries),both

def run_lab(cfg:NeutralizationConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    panel,regime,meta=load_inputs(cfg)

    cmp,comp,loo=ensemble_attribution(panel)
    neutral,cohorts=capacity_neutralization(panel,regime)

    cmp.to_csv(outdir/"ensemble_probability_winner_comparison.csv",index=False)
    comp.to_csv(outdir/"ensemble_divergence_component_attribution.csv",index=False)
    loo.to_csv(outdir/"ensemble_leave_one_component_out_attribution.csv",index=False)
    neutral.to_csv(outdir/"capacity_regime_neutralization_summary.csv",index=False)
    cohorts.to_csv(outdir/"capacity_accepted_skipped_with_regimes.csv.gz",index=False,compression="gzip")

    divergence=cmp[cmp["same_symbol"]==False]
    ens_summary={
        "dates":int(len(cmp)),
        "divergence_dates":int(len(divergence)),
        "same_winner_fraction":float(cmp["same_symbol"].mean()) if len(cmp) else np.nan,
        "mean_ensemble_minus_probability_r_on_divergence":float(divergence["ensemble_minus_probability_r"].mean()) if len(divergence) else np.nan,
        "win_fraction_ensemble_beats_probability_on_divergence":float((divergence["ensemble_minus_probability_r"]>0).mean()) if len(divergence) else np.nan,
    }

    # Overall accepted/skipped raw comparison.
    a=cohorts[cohorts["capacity_cohort"]=="ACCEPTED"]
    s=cohorts[cohorts["capacity_cohort"]=="SKIPPED"]
    raw_capacity={
        "accepted_n":int(len(a)),"skipped_n":int(len(s)),
        "accepted_mean_r":float(a["r_multiple"].mean()) if len(a) else np.nan,
        "skipped_mean_r":float(s["r_multiple"].mean()) if len(s) else np.nan,
        "raw_gap_r":float(a["r_multiple"].mean()-s["r_multiple"].mean()) if len(a) and len(s) else np.nan,
    }

    report=[
        "# M77.29.2 Ensemble Attribution & Capacity Regime Neutralization","",
        "## Ensemble vs Probability winner comparison","",_md(cmp.head(40)),"",
        "## Leave-one-component-out attribution","",_md(loo),"",
        "## Capacity neutralization","",_md(neutral),"",
    ]
    (outdir/"ENSEMBLE_ATTRIBUTION_CAPACITY_REGIME_NEUTRALIZATION_REPORT.md").write_text("\n".join(report))

    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31","consumed_2018_2026_rows_read":0,
        "new_rankers_tested":0,"new_thresholds_tested":0,"ensemble_weights_retuned":False,
        "ensemble_attribution":ens_summary,
        "capacity_raw":raw_capacity,
        "capacity_neutralization":neutral.to_dict(orient="records"),
        "regime_columns_used":_discover_regime_columns(regime),
        "m77_23_drv_modified":False,"m77_24_1_psve_modified":False,"m77_26_2_mge_modified":False,"m77_27_1_cqmi_modified":False,
        "production_authority_effect":False,"polygon_api_called":False,
        "next_step":"REVIEW WHETHER ENSEMBLE INDEPENDENCE AND CAPACITY UPLIFT SURVIVE FIXED COMPONENT ATTRIBUTION AND REGIME/CALENDAR NEUTRALIZATION",
        "upstream":meta,
    }
    _atomic_json(outdir/"ensemble_attribution_capacity_neutralization_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{"version":VERSION,"config":cfg.__dict__,"summary":summary})
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.29.2 ensemble attribution and capacity regime neutralization")
    p.add_argument("--project-root",required=True)
    p.add_argument("--executable-panel-path",default=NeutralizationConfig.executable_panel_path)
    p.add_argument("--regime-calendar-path",default=NeutralizationConfig.regime_calendar_path)
    p.add_argument("--output-dir",default=NeutralizationConfig.output_dir)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    cfg=NeutralizationConfig(project_root=a.project_root,executable_panel_path=a.executable_panel_path,
                             regime_calendar_path=a.regime_calendar_path,output_dir=a.output_dir)
    print(json.dumps(run_lab(cfg),indent=2,sort_keys=True,default=_json_default))
    return 0
