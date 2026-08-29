from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

VERSION="M77.36.1-CROSS-SECTIONAL-DISPERSION-EXECUTABLE-AUTHORITY-BINDING-REPAIR-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
PRIMARY_HORIZON=60
PRIMARY_TARGET_ATR=5.0
PRIMARY_STOP_ATR=3.0
TOP_Q=0.80
BOTTOM_Q=0.20

# Frozen before outcome inspection.
DATE_STATES=(
    "HIGH_PROBABILITY_DISPERSION",
    "LOW_PROBABILITY_DISPERSION",
    "HIGH_SCORE_DISPERSION",
    "LOW_SCORE_DISPERSION",
    "TOP_CANDIDATE_MARGIN_LARGE",
    "TOP_CANDIDATE_MARGIN_SMALL",
    "CROSS_SECTION_CONCENTRATED",
    "CROSS_SECTION_DIFFUSE",
)

class DispersionOpportunityError(RuntimeError):
    pass

@dataclass(frozen=True)
class DispersionOpportunityConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    output_dir:str="research_data/m77_36/cross_sectional_dispersion_relative_opportunity_edge_discovery"


def _resolve(root:Path,raw:str)->Path:
    p=Path(raw).expanduser()
    return p if p.is_absolute() else root/p

def _json_default(v:Any)->Any:
    if isinstance(v,(np.integer,)): return int(v)
    if isinstance(v,(np.floating,)): return None if not np.isfinite(v) else float(v)
    if isinstance(v,(pd.Timestamp,datetime)): return v.isoformat()
    if isinstance(v,Path): return str(v)
    raise TypeError(type(v).__name__)

def _atomic_json(path:Path,payload:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True,default=_json_default))
    os.replace(tmp,path)

def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def _md(df:pd.DataFrame,n:int=40)->str:
    if df.empty:return "_No rows._"
    x=df.head(n); cols=[str(c) for c in x.columns]
    def f(v):
        if pd.isna(v): return ""
        if isinstance(v,(float,np.floating)): return f"{float(v):.6g}"
        return str(v).replace("|","\\|").replace("\n"," ")
    lines=["| "+" | ".join(cols)+" |","| "+" | ".join("---" for _ in cols)+" |"]
    for _,r in x.iterrows():
        lines.append("| "+" | ".join(f(r[c]) for c in x.columns)+" |")
    return "\n".join(lines)

def _metrics(g:pd.DataFrame)->dict[str,Any]:
    if g.empty:return {"n":0}
    r=pd.to_numeric(g["r_multiple"],errors="coerce").dropna()
    if r.empty:return {"n":0}
    x=g.loc[r.index].copy()
    gp=float(r[r>0].sum()); gl=float(-r[r<0].sum())
    sym=x.assign(_r=r).groupby("symbol")["_r"].mean()
    contrib=x.assign(_r=r).groupby("symbol")["_r"].sum().abs().sort_values(ascending=False)
    denom=float(contrib.sum())
    return {
        "n":int(len(r)),
        "symbols":int(x["symbol"].nunique()),
        "mean_r":float(r.mean()),
        "median_r":float(r.median()),
        "win_rate":float((r>0).mean()),
        "profit_factor":float(gp/gl) if gl>0 else np.inf,
        "equal_symbol_mean_r":float(sym.mean()) if len(sym) else np.nan,
        "positive_symbol_fraction":float((sym>0).mean()) if len(sym) else np.nan,
        "top10_abs_contribution_fraction":float(contrib.head(10).sum()/denom) if denom>0 else np.nan,
    }

def _nonoverlap(g:pd.DataFrame)->pd.DataFrame:
    if g.empty:return g
    z=g.sort_values(["symbol","entry_date","as_of"]).copy()
    keep=[]; last_exit={}
    for idx,row in z.iterrows():
        sym=str(row["symbol"]); entry=pd.Timestamp(row["entry_date"])
        prev=last_exit.get(sym)
        if prev is not None and entry<=prev: continue
        keep.append(idx)
        exit_day=max(1,int(float(row.get("exit_day",PRIMARY_HORIZON))))
        last_exit[sym]=entry+pd.offsets.BDay(exit_day)
    return z.loc[keep].copy()

def load_panel(cfg:DispersionOpportunityConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    ep=_resolve(root,cfg.executable_panel_path)
    if not ep.exists(): raise DispersionOpportunityError(f"Executable Development panel missing: {ep}")

    p=pd.read_csv(ep)
    p["as_of"]=pd.to_datetime(p["as_of"],errors="coerce")
    p["entry_date"]=pd.to_datetime(p["entry_date"],errors="coerce")
    p=p[
        (pd.to_numeric(p["horizon"],errors="coerce")==PRIMARY_HORIZON)
        &(pd.to_numeric(p["target_atr"],errors="coerce")==PRIMARY_TARGET_ATR)
        &(pd.to_numeric(p["stop_atr"],errors="coerce")==PRIMARY_STOP_ATR)
    ].copy()
    if p.empty: raise DispersionOpportunityError("Frozen executable cohort missing")
    if (p["as_of"]>DEVELOPMENT_END).any():
        raise DispersionOpportunityError("M77.36 refuses post-2017 evidence")

    # M77.26.1 persisted the exact candidate authority fields used by M77.29:
    # probability_up and overall_score. M77.36 must bind directly to that executable
    # authority rather than incorrectly joining the M77.21 raw feature panel.
    required=("symbol","as_of","probability_up","overall_score","r_multiple")
    missing=[c for c in required if c not in p.columns]
    if missing:
        raise DispersionOpportunityError(
            f"M77.26.1 executable authority missing required opportunity fields: {missing}"
        )

    p["symbol"]=p["symbol"].astype(str).str.upper()
    for c in ("probability_up","overall_score","r_multiple"):
        p[c]=pd.to_numeric(p[c],errors="coerce").replace([np.inf,-np.inf],np.nan)

    complete=p[["probability_up","overall_score"]].notna().all(axis=1)
    if (~complete).any():
        detail=[]
        for _,row in p.loc[~complete,["symbol","as_of","probability_up","overall_score"]].head(20).iterrows():
            detail.append({
                "symbol":row["symbol"],"as_of":row["as_of"],
                "missing_fields":[c for c in ("probability_up","overall_score") if pd.isna(row[c])]
            })
        raise DispersionOpportunityError(
            "M77.36 executable opportunity-authority parity failed; "
            f"missing_rows={int((~complete).sum())}, sample={detail}"
        )

    # Per-date cross-sectional opportunity structure.
    date_rows=[]
    for d,g in p.groupby("as_of"):
        prob=g["probability_up"].dropna()
        score=g["overall_score"].dropna()
        if len(prob)<3 or len(score)<3:
            continue
        prob_sorted=np.sort(prob.to_numpy())[::-1]
        score_sorted=np.sort(score.to_numpy())[::-1]
        # HHI on positive shifted probability weights to characterize concentration.
        w=prob.to_numpy().astype(float)
        w=w-np.nanmin(w)+1e-9
        w=w/w.sum()
        date_rows.append({
            "as_of":d,
            "candidate_n":int(len(g)),
            "probability_dispersion":float(prob.std(ddof=0)),
            "score_dispersion":float(score.std(ddof=0)),
            "top_probability_margin":float(prob_sorted[0]-prob_sorted[1]),
            "top_score_margin":float(score_sorted[0]-score_sorted[1]),
            "probability_hhi":float(np.sum(w*w)),
        })
    ds=pd.DataFrame(date_rows)
    if ds.empty:
        raise DispersionOpportunityError("No same-date dispersion states materialized")

    for raw,rank in (
        ("probability_dispersion","prob_disp_rank"),
        ("score_dispersion","score_disp_rank"),
        ("top_probability_margin","top_margin_rank"),
        ("probability_hhi","concentration_rank"),
    ):
        ds[rank]=ds[raw].rank(pct=True,method="average")

    p=p.merge(ds,on="as_of",how="inner",validate="many_to_one")
    p["calendar_year"]=p["as_of"].dt.year
    p["calendar_month"]=p["as_of"].dt.to_period("M").astype(str)

    return p,{
        "rows":int(len(p)),
        "symbols":int(p["symbol"].nunique()),
        "dates":int(p["as_of"].nunique()),
        "first_as_of":p["as_of"].min().date().isoformat(),
        "last_as_of":p["as_of"].max().date().isoformat(),
        "executable_input_sha256":_sha(ep),
        "opportunity_authority_source":"M77.26.1_EXECUTABLE_PANEL",
        "opportunity_fields":["probability_up","overall_score"],
        "opportunity_authority_rows":int(len(p)),
        "opportunity_authority_complete_rows":int(complete.sum()),
        "opportunity_authority_missing_rows":int((~complete).sum()),
        # Backward-compatible aliases used by prior review commands.
        "feature_join_rows":int(len(p)),
        "feature_join_complete_rows":int(complete.sum()),
        "feature_join_missing_rows":int((~complete).sum()),
        "consumed_2018_2026_rows_read":0,
    }

def _state_mask(p:pd.DataFrame,state:str)->pd.Series:
    if state=="HIGH_PROBABILITY_DISPERSION": return p["prob_disp_rank"]>=TOP_Q
    if state=="LOW_PROBABILITY_DISPERSION": return p["prob_disp_rank"]<=BOTTOM_Q
    if state=="HIGH_SCORE_DISPERSION": return p["score_disp_rank"]>=TOP_Q
    if state=="LOW_SCORE_DISPERSION": return p["score_disp_rank"]<=BOTTOM_Q
    if state=="TOP_CANDIDATE_MARGIN_LARGE": return p["top_margin_rank"]>=TOP_Q
    if state=="TOP_CANDIDATE_MARGIN_SMALL": return p["top_margin_rank"]<=BOTTOM_Q
    if state=="CROSS_SECTION_CONCENTRATED": return p["concentration_rank"]>=TOP_Q
    if state=="CROSS_SECTION_DIFFUSE": return p["concentration_rank"]<=BOTTOM_Q
    raise KeyError(state)

def _paired_date_uplift(p:pd.DataFrame,mask:pd.Series)->dict[str,Any]:
    rows=[]
    for d,g in p.groupby("as_of"):
        m=mask.loc[g.index]
        a=g[m]; b=g[~m]
        ar=pd.to_numeric(a["r_multiple"],errors="coerce").dropna()
        br=pd.to_numeric(b["r_multiple"],errors="coerce").dropna()
        if ar.empty or br.empty: continue
        rows.append((d,len(ar),len(br),float(ar.mean()-br.mean())))
    if not rows:return {"paired_dates":0}
    x=pd.DataFrame(rows,columns=["as_of","selected_n","complement_n","uplift"])
    w=np.minimum(x["selected_n"],x["complement_n"]).astype(float)
    return {
        "paired_dates":int(len(x)),
        "equal_date_mean_uplift_r":float(x["uplift"].mean()),
        "matched_size_weighted_uplift_r":float(np.average(x["uplift"],weights=w)) if w.sum()>0 else np.nan,
        "positive_uplift_date_fraction":float((x["uplift"]>0).mean()),
    }

def evaluate_states(p:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    rows=[]; years=[]; months=[]
    baseline=_metrics(p)
    for state in DATE_STATES:
        mask=_state_mask(p,state).fillna(False)
        selected=p[mask].copy(); complement=p[~mask].copy()
        m=_metrics(selected); c=_metrics(complement); nm=_metrics(_nonoverlap(selected))
        paired=_paired_date_uplift(p,mask)
        rows.append({
            "state":state,**m,
            "baseline_mean_r":baseline.get("mean_r"),
            "complement_mean_r":c.get("mean_r"),
            "mean_r_uplift_vs_full":m.get("mean_r",np.nan)-baseline.get("mean_r",np.nan),
            "mean_r_uplift_vs_complement":m.get("mean_r",np.nan)-c.get("mean_r",np.nan),
            "profit_factor_uplift_vs_complement":m.get("profit_factor",np.nan)-c.get("profit_factor",np.nan),
            "nonoverlap_n":nm.get("n",0),
            "nonoverlap_mean_r":nm.get("mean_r",np.nan),
            "nonoverlap_profit_factor":nm.get("profit_factor",np.nan),
            **paired,
        })
        for year,g in p.groupby("calendar_year"):
            mm=_state_mask(g,state).fillna(False)
            a=_metrics(g[mm]); b=_metrics(g[~mm])
            years.append({
                "state":state,"year":int(year),"selected_n":a.get("n",0),
                "mean_r":a.get("mean_r",np.nan),
                "mean_r_uplift_vs_complement":a.get("mean_r",np.nan)-b.get("mean_r",np.nan),
                "profit_factor":a.get("profit_factor",np.nan),
            })
        for month,g in p.groupby("calendar_month"):
            mm=_state_mask(g,state).fillna(False)
            a=_metrics(g[mm]); b=_metrics(g[~mm])
            months.append({
                "state":state,"month":month,"selected_n":a.get("n",0),
                "mean_r":a.get("mean_r",np.nan),
                "mean_r_uplift_vs_complement":a.get("mean_r",np.nan)-b.get("mean_r",np.nan),
            })
    return pd.DataFrame(rows),pd.DataFrame(years),pd.DataFrame(months)

def build_readiness(evidence:pd.DataFrame,years:pd.DataFrame,months:pd.DataFrame)->pd.DataFrame:
    y=years.assign(
        positive=lambda x:(x["mean_r"]>0)&(x["mean_r_uplift_vs_complement"]>0)
    ).groupby("state")["positive"].agg(["sum","count"]).reset_index()
    y["positive_year_fraction"]=y["sum"]/y["count"].replace(0,np.nan)
    mo=months.assign(
        positive=lambda x:(x["mean_r"]>0)&(x["mean_r_uplift_vs_complement"]>0)
    ).groupby("state")["positive"].agg(["sum","count"]).reset_index()
    mo["positive_month_fraction"]=mo["sum"]/mo["count"].replace(0,np.nan)

    out=evidence.merge(y[["state","positive_year_fraction"]],on="state",how="left").merge(
        mo[["state","positive_month_fraction"]],on="state",how="left"
    )
    out["gate_n"]=out["n"]>=2000
    out["gate_symbols"]=out["symbols"]>=250
    out["gate_mean_r"]=out["mean_r"]>=0.20
    out["gate_uplift_vs_complement"]=out["mean_r_uplift_vs_complement"]>=0.04
    out["gate_profit_factor"]=out["profit_factor"]>=1.35
    out["gate_equal_symbol"]=out["equal_symbol_mean_r"]>=0.15
    out["gate_positive_years"]=out["positive_year_fraction"]>=0.70
    out["gate_positive_months"]=out["positive_month_fraction"]>=0.60
    out["gate_nonoverlap_mean_r"]=out["nonoverlap_mean_r"]>=0.15
    out["gate_nonoverlap_pf"]=out["nonoverlap_profit_factor"]>=1.25
    out["gate_concentration"]=out["top10_abs_contribution_fraction"]<=0.25
    gates=[c for c in out.columns if c.startswith("gate_")]
    out["development_ready_dispersion_state"]=out[gates].all(axis=1)
    return out.sort_values(
        ["development_ready_dispersion_state","mean_r_uplift_vs_complement","mean_r"],
        ascending=[False,False,False]
    ).reset_index(drop=True)

def run_lab(cfg:DispersionOpportunityConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir); outdir.mkdir(parents=True,exist_ok=True)
    p,meta=load_panel(cfg)
    evidence,years,months=evaluate_states(p)
    ready=build_readiness(evidence,years,months)

    evidence.to_csv(outdir/"cross_sectional_dispersion_evidence.csv",index=False)
    years.to_csv(outdir/"cross_sectional_dispersion_year_evidence.csv",index=False)
    months.to_csv(outdir/"cross_sectional_dispersion_month_evidence.csv",index=False)
    ready.to_csv(outdir/"cross_sectional_dispersion_readiness.csv",index=False)
    p[[
        "symbol","as_of","entry_date","probability_up","overall_score",
        "candidate_n","probability_dispersion","score_dispersion","top_probability_margin",
        "top_score_margin","probability_hhi","prob_disp_rank","score_disp_rank",
        "top_margin_rank","concentration_rank","r_multiple"
    ]].to_csv(outdir/"point_in_time_cross_sectional_dispersion_panel.csv.gz",index=False,compression="gzip")

    best=ready[ready["development_ready_dispersion_state"]==True].head(1)
    report=[
        "# M77.36 Cross-Sectional Dispersion & Relative Opportunity Edge Discovery","",
        "## Frozen design","",
        "- Development evidence only through 2017-12-31.",
        "- Frozen M77.26.1 NEXT_OPEN / 5ATR / 3ATR / 60-session executable outcome.",
        "- Same-date candidate opportunity structure only.",
        "- No PROBABILITY_UP threshold, Top-K, or management retuning.",
        "- State variables are date-level PIT dispersion/separation/concentration transforms.","",
        "## Readiness","",_md(ready),"",
        "## Year evidence","",_md(years,80),"",
    ]
    (outdir/"CROSS_SECTIONAL_DISPERSION_RELATIVE_OPPORTUNITY_REPORT.md").write_text("\n".join(report))

    summary={
        "version":VERSION,"status":"COMPLETE",
        "completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31",
        "consumed_2018_2026_rows_read":0,
        "frozen_management_geometry":{"entry":"NEXT_OPEN","horizon":60,"target_atr":5.0,"stop_atr":3.0},
        "dispersion_states_tested":list(DATE_STATES),
        "fixed_top_quantile":TOP_Q,"fixed_bottom_quantile":BOTTOM_Q,
        "point_in_time_date_level_states":True,
        "development_ready_dispersion_states":int(ready["development_ready_dispersion_state"].sum()),
        "highest_ranked_development_ready_state":(
            best.iloc[0][[
                "state","n","symbols","mean_r","profit_factor","mean_r_uplift_vs_complement",
                "nonoverlap_mean_r","nonoverlap_profit_factor","positive_year_fraction",
                "positive_month_fraction","top10_abs_contribution_fraction"
            ]].to_dict() if not best.empty else None
        ),
        "upstream":meta,
        "m77_23_drv_modified":False,
        "m77_24_1_psve_modified":False,
        "m77_26_2_mge_modified":False,
        "m77_27_1_cqmi_modified":False,
        "m77_30_cpre_modified":False,
        "m77_30_cpre_read":False,
        "new_probability_up_thresholds_tested":0,
        "new_top_k_values_tested":0,
        "management_geometry_retuned":False,
        "automatic_retraining":False,
        "polygon_api_called":False,
        "production_authority_effect":False,
        "next_step":"REVIEW DEVELOPMENT-ONLY CROSS-SECTIONAL DISPERSION/SEPARATION EVIDENCE; ANY SURVIVOR IS HYPOTHESIS-GENERATING AND REQUIRES SEPARATE PROSPECTIVE GOVERNANCE",
    }
    _atomic_json(outdir/"cross_sectional_dispersion_relative_opportunity_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{
        "version":VERSION,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "config":cfg.__dict__,
        "frozen_states":list(DATE_STATES),
        "fixed_top_quantile":TOP_Q,
        "fixed_bottom_quantile":BOTTOM_Q,
        "upstream":meta,
        "forbidden_outcome_window":"2018-01-01 THROUGH 2026-12-31",
        "production_authority_effect":False,
    })
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.36 cross-sectional dispersion and relative opportunity edge discovery")
    p.add_argument("--project-root",required=True)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    print(json.dumps(run_lab(DispersionOpportunityConfig(project_root=a.project_root)),indent=2,sort_keys=True,default=_json_default))
    return 0
