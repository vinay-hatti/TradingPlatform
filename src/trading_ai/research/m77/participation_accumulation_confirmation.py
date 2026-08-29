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

VERSION="M77.33.2-PARTICIPATION-STATE-SPECIFIC-FEATURE-PARITY-REPAIR-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
PRIMARY_HORIZON=60
PRIMARY_TARGET_ATR=5.0
PRIMARY_STOP_ATR=3.0
TOP_Q=0.80
BOTTOM_Q=0.20

# Frozen before Development outcome inspection.
PARTICIPATION_STATES=(
    "VOLUME_RATIO_20_TOP20",
    "VOLUME_RATIO_PERSISTENCE_TOP20",
    "VOLUME_ACCELERATION_TOP20",
    "VOLUME_DECELERATION_BOTTOM20",
    "ACCUMULATION_CONFIRMATION",
    "DISTRIBUTION_WARNING",
)

class ParticipationError(RuntimeError):
    pass

@dataclass(frozen=True)
class ParticipationConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    feature_authority_path:str="research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz"
    output_dir:str="research_data/m77_33/participation_accumulation_confirmation_edge_discovery"


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
        if prev is not None and entry<=prev: continue
        keep.append(idx)
        exit_day=max(1,int(float(row.get("exit_day",PRIMARY_HORIZON))))
        last_exit[sym]=entry+pd.offsets.BDay(exit_day)
    return z.loc[keep].copy()

def load_panel(cfg:ParticipationConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    ep=_resolve(root,cfg.executable_panel_path)
    ap=_resolve(root,cfg.feature_authority_path)
    if not ep.exists():raise ParticipationError(f"Executable Development panel missing: {ep}")
    if not ap.exists():raise ParticipationError(f"Frozen M77.21 feature authority missing: {ap}")

    p=pd.read_csv(ep)
    p["as_of"]=pd.to_datetime(p["as_of"],errors="coerce")
    p["entry_date"]=pd.to_datetime(p["entry_date"],errors="coerce")
    p=p[
        (pd.to_numeric(p["horizon"],errors="coerce")==PRIMARY_HORIZON)
        &(pd.to_numeric(p["target_atr"],errors="coerce")==PRIMARY_TARGET_ATR)
        &(pd.to_numeric(p["stop_atr"],errors="coerce")==PRIMARY_STOP_ATR)
    ].copy()
    if p.empty:raise ParticipationError("Frozen executable cohort missing")
    if (p["as_of"]>DEVELOPMENT_END).any():
        raise ParticipationError("M77.33 refuses post-2017 executable evidence")

    auth=pd.read_pickle(ap,compression="gzip")
    auth=auth.copy()
    auth["symbol"]=auth["symbol"].astype(str).str.upper()
    auth["as_of"]=pd.to_datetime(auth["as_of"],errors="coerce")

    globally_required_features=(
        "volume_ratio_10","volume_ratio_20","volume_ratio_60",
    )
    state_specific_features=("clv",)
    optional_diagnostic_features=(
        "volume_z_10","volume_z_20","volume_z_60","body_range",
    )
    missing=[c for c in ("symbol","as_of",*globally_required_features,*state_specific_features) if c not in auth.columns]
    if missing:
        raise ParticipationError(f"M77.21 feature authority missing required participation columns: {missing}")

    available_optional=[c for c in optional_diagnostic_features if c in auth.columns]
    auth=auth[["symbol","as_of",*globally_required_features,*state_specific_features,*available_optional]].copy()
    if auth.duplicated(["symbol","as_of"],keep=False).any():
        raise ParticipationError("M77.21 feature authority is not unique on (symbol, as_of)")

    p["symbol"]=p["symbol"].astype(str).str.upper()
    p=p.merge(auth,on=["symbol","as_of"],how="left",validate="many_to_one")
    global_complete=p[list(globally_required_features)].notna().all(axis=1)
    if (~global_complete).any():
        missing_detail=[]
        for _,row in p.loc[~global_complete,["symbol","as_of",*globally_required_features]].head(20).iterrows():
            missing_detail.append({
                "symbol":row["symbol"],
                "as_of":row["as_of"],
                "missing_required_features":[c for c in globally_required_features if pd.isna(row[c])],
            })
        raise ParticipationError(
            "M77.33 globally-required point-in-time feature parity failed; "
            f"missing_rows={int((~global_complete).sum())}, sample={missing_detail}"
        )

    for c in optional_diagnostic_features:
        if c not in p.columns:
            p[c]=np.nan

    for c in (*globally_required_features,*state_specific_features,*optional_diagnostic_features,"r_multiple"):
        p[c]=pd.to_numeric(p[c],errors="coerce").replace([np.inf,-np.inf],np.nan)

    clv_complete=p["clv"].notna()
    optional_missing_counts={c:int(p[c].isna().sum()) for c in optional_diagnostic_features}

    eps=1e-12
    p["volume_persistence"]=(p["volume_ratio_10"]+p["volume_ratio_20"]+p["volume_ratio_60"])/3.0
    p["volume_accel_10_vs_60"]=p["volume_ratio_10"]/(p["volume_ratio_60"].abs()+eps)

    # Same-date point-in-time cross-sectional ranks.
    p["vol20_rank"]=p.groupby("as_of")["volume_ratio_20"].rank(pct=True,method="average")
    p["vol_persist_rank"]=p.groupby("as_of")["volume_persistence"].rank(pct=True,method="average")
    p["vol_accel_rank"]=p.groupby("as_of")["volume_accel_10_vs_60"].rank(pct=True,method="average")
    p["clv_rank"]=p.groupby("as_of")["clv"].rank(pct=True,method="average")
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
        "globally_required_feature_join_complete_rows":int(global_complete.sum()),
        "globally_required_feature_join_missing_rows":int((~global_complete).sum()),
        "globally_required_features":list(globally_required_features),
        "clv_available_rows":int(clv_complete.sum()),
        "clv_missing_rows":int((~clv_complete).sum()),
        "clv_coverage_fraction":float(clv_complete.mean()),
        "clv_dependent_states":["ACCUMULATION_CONFIRMATION","DISTRIBUTION_WARNING"],
        "optional_diagnostic_features":list(optional_diagnostic_features),
        "optional_diagnostic_missing_counts":optional_missing_counts,

        # Backward-compatible aliases from M77.33.1.
        "required_feature_join_complete_rows":int(global_complete.sum()),
        "required_feature_join_missing_rows":int((~global_complete).sum()),
        "required_features":list(globally_required_features),
        "feature_join_complete_rows":int(global_complete.sum()),
        "feature_join_missing_rows":int((~global_complete).sum()),
        "consumed_2018_2026_rows_read":0,
    }

def _state_eligible_mask(p:pd.DataFrame,state:str)->pd.Series:
    base=p[["volume_ratio_10","volume_ratio_20","volume_ratio_60"]].notna().all(axis=1)
    if state in ("ACCUMULATION_CONFIRMATION","DISTRIBUTION_WARNING"):
        return base & p["clv"].notna()
    return base


def _state_mask(p:pd.DataFrame,state:str)->pd.Series:
    if state=="VOLUME_RATIO_20_TOP20":
        return p["vol20_rank"]>=TOP_Q
    if state=="VOLUME_RATIO_PERSISTENCE_TOP20":
        return p["vol_persist_rank"]>=TOP_Q
    if state=="VOLUME_ACCELERATION_TOP20":
        return p["vol_accel_rank"]>=TOP_Q
    if state=="VOLUME_DECELERATION_BOTTOM20":
        return p["vol_accel_rank"]<=BOTTOM_Q
    if state=="ACCUMULATION_CONFIRMATION":
        return (p["vol_persist_rank"]>=TOP_Q)&(p["clv_rank"]>=TOP_Q)
    if state=="DISTRIBUTION_WARNING":
        return (p["vol_persist_rank"]>=TOP_Q)&(p["clv_rank"]<=BOTTOM_Q)
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
    for state in PARTICIPATION_STATES:
        eligible=_state_eligible_mask(p,state).fillna(False)
        pe=p[eligible].copy()
        mask=_state_mask(pe,state).fillna(False)
        selected=pe[mask].copy();complement=pe[~mask].copy()
        m=_metrics(selected);c=_metrics(complement);nm=_metrics(_nonoverlap(selected))
        paired=_paired_date_uplift(pe,mask)
        rows.append({
            "state":state,
            "eligible_n":int(len(pe)),
            "excluded_missing_state_features_n":int((~eligible).sum()),
            **m,
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
            ge=g[_state_eligible_mask(g,state).fillna(False)].copy()
            mm=_state_mask(ge,state).fillna(False)
            a=_metrics(ge[mm]);b=_metrics(ge[~mm])
            years.append({
                "state":state,"year":int(year),"selected_n":a.get("n",0),
                "mean_r":a.get("mean_r",np.nan),
                "mean_r_uplift_vs_complement":a.get("mean_r",np.nan)-b.get("mean_r",np.nan),
                "profit_factor":a.get("profit_factor",np.nan),
            })
        for month,g in p.groupby("calendar_month"):
            ge=g[_state_eligible_mask(g,state).fillna(False)].copy()
            mm=_state_mask(ge,state).fillna(False)
            a=_metrics(ge[mm]);b=_metrics(ge[~mm])
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
    composite=out["state"].isin(["ACCUMULATION_CONFIRMATION","DISTRIBUTION_WARNING"])
    out["gate_n"]=np.where(composite,out["n"]>=500,out["n"]>=1000)
    out["gate_symbols"]=np.where(composite,out["symbols"]>=150,out["symbols"]>=200)
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
    out["development_ready_participation_state"]=out[gates].all(axis=1)
    return out.sort_values(
        ["development_ready_participation_state","mean_r_uplift_vs_complement","mean_r"],
        ascending=[False,False,False]
    ).reset_index(drop=True)

def run_lab(cfg:ParticipationConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    p,meta=load_panel(cfg)
    evidence,years,months=evaluate_states(p)
    ready=build_readiness(evidence,years,months)

    evidence.to_csv(outdir/"participation_accumulation_evidence.csv",index=False)
    years.to_csv(outdir/"participation_accumulation_year_evidence.csv",index=False)
    months.to_csv(outdir/"participation_accumulation_month_evidence.csv",index=False)
    ready.to_csv(outdir/"participation_accumulation_readiness.csv",index=False)
    p[[
        "symbol","as_of","entry_date","volume_ratio_10","volume_ratio_20","volume_ratio_60",
        "volume_z_10","volume_z_20","volume_z_60","clv","body_range",
        "volume_persistence","volume_accel_10_vs_60","vol20_rank","vol_persist_rank",
        "vol_accel_rank","clv_rank","r_multiple"
    ]].to_csv(outdir/"point_in_time_participation_state_panel.csv.gz",index=False,compression="gzip")

    best=ready[ready["development_ready_participation_state"]==True].head(1)
    report=[
        "# M77.33 Participation & Accumulation Confirmation Edge Discovery","",
        "## Frozen design","",
        "- Development evidence only through 2017-12-31.",
        "- Frozen M77.26.1 NEXT_OPEN / 5ATR / 3ATR / 60-session executable outcome.",
        "- Frozen M77.21 point-in-time participation features.",
        "- No PROBABILITY_UP threshold, Top-K, or management retuning.",
        "- Participation and CLV states are same-date point-in-time cross-sectional transforms.","",
        "## Readiness","",_md(ready),"",
        "## Year evidence","",_md(years,80),"",
    ]
    (outdir/"PARTICIPATION_ACCUMULATION_CONFIRMATION_REPORT.md").write_text("\n".join(report))

    summary={
        "version":VERSION,"status":"COMPLETE",
        "completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31",
        "consumed_2018_2026_rows_read":0,
        "frozen_management_geometry":{"entry":"NEXT_OPEN","horizon":60,"target_atr":5.0,"stop_atr":3.0},
        "participation_states_tested":list(PARTICIPATION_STATES),
        "fixed_top_quantile":TOP_Q,"fixed_bottom_quantile":BOTTOM_Q,
        "point_in_time_cross_sectional_ranks":True,
        "development_ready_participation_states":int(ready["development_ready_participation_state"].sum()),
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
        "next_step":"REVIEW DEVELOPMENT-ONLY PARTICIPATION/ACCUMULATION EVIDENCE; ANY SURVIVOR IS HYPOTHESIS-GENERATING AND REQUIRES SEPARATE PROSPECTIVE GOVERNANCE",
    }
    _atomic_json(outdir/"participation_accumulation_confirmation_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{
        "version":VERSION,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "config":cfg.__dict__,
        "frozen_states":list(PARTICIPATION_STATES),
        "fixed_top_quantile":TOP_Q,
        "fixed_bottom_quantile":BOTTOM_Q,
        "upstream":meta,
        "forbidden_outcome_window":"2018-01-01 THROUGH 2026-12-31",
        "production_authority_effect":False,
    })
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.33 participation/accumulation confirmation edge discovery")
    p.add_argument("--project-root",required=True)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    print(json.dumps(run_lab(ParticipationConfig(project_root=a.project_root)),indent=2,sort_keys=True,default=_json_default))
    return 0
