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

VERSION="M77.34.0-MEAN-REVERSION-EXTENSION-STATE-EDGE-DISCOVERY-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
PRIMARY_HORIZON=60
PRIMARY_TARGET_ATR=5.0
PRIMARY_STOP_ATR=3.0
TOP_Q=0.80
BOTTOM_Q=0.20

# Frozen before outcome inspection.
STATES=(
    "EXTENDED_ABOVE_20D_TOP20",
    "EXTENDED_BELOW_20D_BOTTOM20",
    "EXTENDED_ABOVE_60D_TOP20",
    "EXTENDED_BELOW_60D_BOTTOM20",
    "NEAR_20D_HIGH_TOP20",
    "NEAR_20D_LOW_BOTTOM20",
    "MULTI_HORIZON_EXTENSION",
    "MULTI_HORIZON_MEAN_REVERSION",
)

class MeanReversionExtensionError(RuntimeError):
    pass

@dataclass(frozen=True)
class MeanReversionExtensionConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    feature_authority_path:str="research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz"
    output_dir:str="research_data/m77_34/mean_reversion_extension_state_edge_discovery"


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

def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def _md(df:pd.DataFrame,n:int=40)->str:
    if df.empty:return "_No rows._"
    x=df.head(n)
    cols=[str(c) for c in x.columns]
    def f(v):
        if pd.isna(v):return ""
        if isinstance(v,(float,np.floating)):return f"{float(v):.6g}"
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
    keep=[];last_exit={}
    for idx,row in z.iterrows():
        sym=str(row["symbol"]); entry=pd.Timestamp(row["entry_date"])
        prev=last_exit.get(sym)
        if prev is not None and entry<=prev:continue
        keep.append(idx)
        exit_day=max(1,int(float(row.get("exit_day",PRIMARY_HORIZON))))
        last_exit[sym]=entry+pd.offsets.BDay(exit_day)
    return z.loc[keep].copy()

def load_panel(cfg:MeanReversionExtensionConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    ep=_resolve(root,cfg.executable_panel_path)
    ap=_resolve(root,cfg.feature_authority_path)
    if not ep.exists():raise MeanReversionExtensionError(f"Executable Development panel missing: {ep}")
    if not ap.exists():raise MeanReversionExtensionError(f"Frozen M77.21 feature authority missing: {ap}")

    p=pd.read_csv(ep)
    p["as_of"]=pd.to_datetime(p["as_of"],errors="coerce")
    p["entry_date"]=pd.to_datetime(p["entry_date"],errors="coerce")
    p=p[
        (pd.to_numeric(p["horizon"],errors="coerce")==PRIMARY_HORIZON)
        &(pd.to_numeric(p["target_atr"],errors="coerce")==PRIMARY_TARGET_ATR)
        &(pd.to_numeric(p["stop_atr"],errors="coerce")==PRIMARY_STOP_ATR)
    ].copy()
    if p.empty:raise MeanReversionExtensionError("Frozen executable cohort missing")
    if (p["as_of"]>DEVELOPMENT_END).any():
        raise MeanReversionExtensionError("M77.34 refuses post-2017 evidence")

    auth=pd.read_pickle(ap,compression="gzip").copy()
    auth["symbol"]=auth["symbol"].astype(str).str.upper()
    auth["as_of"]=pd.to_datetime(auth["as_of"],errors="coerce")

    features=(
        "dist_sma_20","dist_sma_60","dist_ema_21","dist_ema_50",
        "dist_prev_high_20","dist_prev_low_20",
        "dist_prev_high_60","dist_prev_low_60",
    )
    missing=[c for c in ("symbol","as_of",*features) if c not in auth.columns]
    if missing:
        raise MeanReversionExtensionError(f"M77.21 feature authority missing required extension features: {missing}")

    auth=auth[["symbol","as_of",*features]].copy()
    if auth.duplicated(["symbol","as_of"],keep=False).any():
        raise MeanReversionExtensionError("M77.21 feature authority is not unique on (symbol, as_of)")

    p["symbol"]=p["symbol"].astype(str).str.upper()
    p=p.merge(auth,on=["symbol","as_of"],how="left",validate="many_to_one")

    complete=p[list(features)].notna().all(axis=1)
    if (~complete).any():
        detail=[]
        for _,row in p.loc[~complete,["symbol","as_of",*features]].head(20).iterrows():
            detail.append({
                "symbol":row["symbol"],"as_of":row["as_of"],
                "missing_features":[c for c in features if pd.isna(row[c])]
            })
        raise MeanReversionExtensionError(
            f"M77.34 point-in-time feature parity failed; missing_rows={int((~complete).sum())}, sample={detail}"
        )

    for c in (*features,"r_multiple"):
        p[c]=pd.to_numeric(p[c],errors="coerce").replace([np.inf,-np.inf],np.nan)

    # Same-date point-in-time cross-sectional ranks.
    p["dist20_rank"]=p.groupby("as_of")["dist_sma_20"].rank(pct=True,method="average")
    p["dist60_rank"]=p.groupby("as_of")["dist_sma_60"].rank(pct=True,method="average")
    # Closer to prior high means less negative / larger dist_prev_high.
    p["near_high20_rank"]=p.groupby("as_of")["dist_prev_high_20"].rank(pct=True,method="average")
    # Closer to prior low means smaller positive / more negative dist_prev_low.
    p["near_low20_rank"]=p.groupby("as_of")["dist_prev_low_20"].rank(pct=True,method="average")

    p["multi_extension_score"]=(p["dist20_rank"]+p["dist60_rank"])/2.0
    p["multi_mean_reversion_score"]=1.0-p["multi_extension_score"]

    p["calendar_year"]=p["as_of"].dt.year
    p["calendar_month"]=p["as_of"].dt.to_period("M").astype(str)

    return p,{
        "rows":int(len(p)),
        "symbols":int(p["symbol"].nunique()),
        "first_as_of":p["as_of"].min().date().isoformat(),
        "last_as_of":p["as_of"].max().date().isoformat(),
        "executable_input_sha256":_sha(ep),
        "feature_authority_sha256":_sha(ap),
        "feature_authority_rows":int(len(auth)),
        "feature_join_rows":int(len(p)),
        "feature_join_complete_rows":int(complete.sum()),
        "feature_join_missing_rows":int((~complete).sum()),
        "consumed_2018_2026_rows_read":0,
    }

def _state_mask(p:pd.DataFrame,state:str)->pd.Series:
    if state=="EXTENDED_ABOVE_20D_TOP20":return p["dist20_rank"]>=TOP_Q
    if state=="EXTENDED_BELOW_20D_BOTTOM20":return p["dist20_rank"]<=BOTTOM_Q
    if state=="EXTENDED_ABOVE_60D_TOP20":return p["dist60_rank"]>=TOP_Q
    if state=="EXTENDED_BELOW_60D_BOTTOM20":return p["dist60_rank"]<=BOTTOM_Q
    if state=="NEAR_20D_HIGH_TOP20":return p["near_high20_rank"]>=TOP_Q
    if state=="NEAR_20D_LOW_BOTTOM20":return p["near_low20_rank"]<=BOTTOM_Q
    if state=="MULTI_HORIZON_EXTENSION":return p["multi_extension_score"]>=TOP_Q
    if state=="MULTI_HORIZON_MEAN_REVERSION":return p["multi_mean_reversion_score"]>=TOP_Q
    raise KeyError(state)

def _paired_date_uplift(p:pd.DataFrame,mask:pd.Series)->dict[str,Any]:
    rows=[]
    for d,g in p.groupby("as_of"):
        m=mask.loc[g.index]
        a=g[m];b=g[~m]
        ar=pd.to_numeric(a["r_multiple"],errors="coerce").dropna()
        br=pd.to_numeric(b["r_multiple"],errors="coerce").dropna()
        if ar.empty or br.empty:continue
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
    rows=[];years=[];months=[]
    baseline=_metrics(p)
    for state in STATES:
        mask=_state_mask(p,state).fillna(False)
        selected=p[mask].copy(); complement=p[~mask].copy()
        m=_metrics(selected);c=_metrics(complement);nm=_metrics(_nonoverlap(selected))
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
            a=_metrics(g[mm]);b=_metrics(g[~mm])
            years.append({
                "state":state,"year":int(year),"selected_n":a.get("n",0),
                "mean_r":a.get("mean_r",np.nan),
                "mean_r_uplift_vs_complement":a.get("mean_r",np.nan)-b.get("mean_r",np.nan),
                "profit_factor":a.get("profit_factor",np.nan),
            })
        for month,g in p.groupby("calendar_month"):
            mm=_state_mask(g,state).fillna(False)
            a=_metrics(g[mm]);b=_metrics(g[~mm])
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
    out["gate_n"]=out["n"]>=1000
    out["gate_symbols"]=out["symbols"]>=200
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
    out["development_ready_extension_state"]=out[gates].all(axis=1)
    return out.sort_values(
        ["development_ready_extension_state","mean_r_uplift_vs_complement","mean_r"],
        ascending=[False,False,False]
    ).reset_index(drop=True)

def run_lab(cfg:MeanReversionExtensionConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    p,meta=load_panel(cfg)
    evidence,years,months=evaluate_states(p)
    ready=build_readiness(evidence,years,months)

    evidence.to_csv(outdir/"mean_reversion_extension_evidence.csv",index=False)
    years.to_csv(outdir/"mean_reversion_extension_year_evidence.csv",index=False)
    months.to_csv(outdir/"mean_reversion_extension_month_evidence.csv",index=False)
    ready.to_csv(outdir/"mean_reversion_extension_readiness.csv",index=False)
    p[[
        "symbol","as_of","entry_date",
        "dist_sma_20","dist_sma_60","dist_ema_21","dist_ema_50",
        "dist_prev_high_20","dist_prev_low_20","dist_prev_high_60","dist_prev_low_60",
        "dist20_rank","dist60_rank","near_high20_rank","near_low20_rank",
        "multi_extension_score","multi_mean_reversion_score","r_multiple"
    ]].to_csv(outdir/"point_in_time_mean_reversion_extension_panel.csv.gz",index=False,compression="gzip")

    best=ready[ready["development_ready_extension_state"]==True].head(1)
    report=[
        "# M77.34 Mean-Reversion / Extension State Edge Discovery","",
        "## Frozen design","",
        "- Development evidence only through 2017-12-31.",
        "- Frozen M77.26.1 NEXT_OPEN / 5ATR / 3ATR / 60-session executable outcome.",
        "- Frozen M77.21 point-in-time extension/reference-distance features.",
        "- No PROBABILITY_UP threshold, Top-K, or management retuning.",
        "- State ranks are same-date point-in-time cross-sectional transforms.","",
        "## Readiness","",_md(ready),"",
        "## Year evidence","",_md(years,80),"",
    ]
    (outdir/"MEAN_REVERSION_EXTENSION_STATE_REPORT.md").write_text("\n".join(report))

    summary={
        "version":VERSION,"status":"COMPLETE",
        "completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31",
        "consumed_2018_2026_rows_read":0,
        "frozen_management_geometry":{"entry":"NEXT_OPEN","horizon":60,"target_atr":5.0,"stop_atr":3.0},
        "extension_states_tested":list(STATES),
        "fixed_top_quantile":TOP_Q,"fixed_bottom_quantile":BOTTOM_Q,
        "point_in_time_cross_sectional_ranks":True,
        "development_ready_extension_states":int(ready["development_ready_extension_state"].sum()),
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
        "next_step":"REVIEW DEVELOPMENT-ONLY EXTENSION/MEAN-REVERSION EVIDENCE; ANY SURVIVOR IS HYPOTHESIS-GENERATING AND REQUIRES SEPARATE PROSPECTIVE GOVERNANCE",
    }
    _atomic_json(outdir/"mean_reversion_extension_state_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{
        "version":VERSION,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "config":cfg.__dict__,
        "frozen_states":list(STATES),
        "fixed_top_quantile":TOP_Q,
        "fixed_bottom_quantile":BOTTOM_Q,
        "upstream":meta,
        "forbidden_outcome_window":"2018-01-01 THROUGH 2026-12-31",
        "production_authority_effect":False,
    })
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.34 mean-reversion/extension state edge discovery")
    p.add_argument("--project-root",required=True)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    print(json.dumps(run_lab(MeanReversionExtensionConfig(project_root=a.project_root)),indent=2,sort_keys=True,default=_json_default))
    return 0
