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

VERSION="M77.31.1-CROSS-SECTIONAL-RELATIVE-STRENGTH-PIT-FEATURE-AUTHORITY-JOIN-REPAIR-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
PRIMARY_HORIZON=60
PRIMARY_TARGET_ATR=5.0
PRIMARY_STOP_ATR=3.0

# Frozen before Development outcome inspection.
LEADERSHIP_STATES=(
    "RS20_TOP20",
    "RS60_TOP20",
    "RS126_TOP20",
    "PERSIST_20_60_TOP20",
    "PERSIST_20_60_126_TOP20",
    "STABLE_20_60_126_TOP20",
    "ACCEL_20_VS_60_TOP20",
    "DECEL_20_VS_60_BOTTOM20",
)
TOP_Q=0.80
BOTTOM_Q=0.20

class LeadershipError(RuntimeError):
    pass

@dataclass(frozen=True)
class LeadershipConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    feature_authority_path:str="research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz"
    output_dir:str="research_data/m77_31/cross_sectional_relative_strength_persistence_leadership_edge_discovery"


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
    x=df.head(n)
    cols=[str(c) for c in x.columns]
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
    keep=[]
    last_exit={}
    for idx,row in z.iterrows():
        sym=str(row["symbol"])
        entry=pd.Timestamp(row["entry_date"])
        prev=last_exit.get(sym)
        if prev is not None and entry<=prev:
            continue
        keep.append(idx)
        exit_day=max(1,int(float(row.get("exit_day",PRIMARY_HORIZON))))
        last_exit[sym]=entry+pd.offsets.BDay(exit_day)
    return z.loc[keep].copy()

def load_panel(cfg:LeadershipConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    path=_resolve(root,cfg.executable_panel_path)
    if not path.exists():
        raise LeadershipError(f"Executable Development panel missing: {path}")
    p=pd.read_csv(path)
    for c in ("as_of","entry_date"):
        p[c]=pd.to_datetime(p[c],errors="coerce")
    p=p[
        (pd.to_numeric(p["horizon"],errors="coerce")==PRIMARY_HORIZON)
        &(pd.to_numeric(p["target_atr"],errors="coerce")==PRIMARY_TARGET_ATR)
        &(pd.to_numeric(p["stop_atr"],errors="coerce")==PRIMARY_STOP_ATR)
    ].copy()
    if p.empty:
        raise LeadershipError("Frozen NEXT_OPEN / 5ATR / 3ATR / 60-session executable cohort missing")
    if (p["as_of"]>DEVELOPMENT_END).any():
        raise LeadershipError("M77.31 refuses post-2017 evidence")

    base_required=("r_multiple","symbol","as_of","entry_date")
    missing_base=[c for c in base_required if c not in p.columns]
    if missing_base:
        raise LeadershipError(f"M77.31 executable panel missing required columns: {missing_base}")

    feature_cols=("px_ret_20","px_ret_60","px_ret_126")
    missing_features=[c for c in feature_cols if c not in p.columns]
    feature_join_meta={
        "feature_authority_join_performed":False,
        "feature_authority_path":None,
        "feature_authority_sha256":None,
        "feature_authority_rows":0,
        "feature_authority_unique_keys":0,
        "feature_join_rows":int(len(p)),
        "feature_join_complete_rows":0,
        "feature_join_missing_rows":0,
    }
    if missing_features:
        authority_path=_resolve(root,cfg.feature_authority_path)
        if not authority_path.exists():
            raise LeadershipError(
                "M77.31 executable panel does not preserve point-in-time relative-strength "
                f"features {missing_features}; frozen M77.21 feature authority is missing: {authority_path}"
            )
        try:
            authority=pd.read_pickle(authority_path,compression="gzip")
        except Exception as exc:
            raise LeadershipError(
                f"M77.31 could not read frozen M77.21 feature authority {authority_path}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if "symbol" not in authority.columns or "as_of" not in authority.columns:
            raise LeadershipError("M77.21 feature authority missing symbol/as_of identity columns")
        authority=authority.copy()
        authority["symbol"]=authority["symbol"].astype(str).str.upper()
        authority["as_of"]=pd.to_datetime(authority["as_of"],errors="coerce")
        auth_missing=[c for c in feature_cols if c not in authority.columns]
        if auth_missing:
            raise LeadershipError(
                f"M77.21 feature authority missing required leadership features: {auth_missing}"
            )
        authority=authority[["symbol","as_of",*feature_cols]].copy()
        dup=authority.duplicated(["symbol","as_of"],keep=False)
        if dup.any():
            sample=authority.loc[dup,["symbol","as_of"]].head(10).to_dict(orient="records")
            raise LeadershipError(
                f"M77.21 feature authority is not unique on (symbol, as_of); sample={sample}"
            )
        p["symbol"]=p["symbol"].astype(str).str.upper()
        p=p.merge(authority,on=["symbol","as_of"],how="left",validate="many_to_one")
        complete=p[list(feature_cols)].notna().all(axis=1)
        missing_rows=int((~complete).sum())
        feature_join_meta={
            "feature_authority_join_performed":True,
            "feature_authority_path":str(authority_path.relative_to(root)) if authority_path.is_relative_to(root) else str(authority_path),
            "feature_authority_sha256":_sha(authority_path),
            "feature_authority_rows":int(len(authority)),
            "feature_authority_unique_keys":int(authority[["symbol","as_of"]].drop_duplicates().shape[0]),
            "feature_join_rows":int(len(p)),
            "feature_join_complete_rows":int(complete.sum()),
            "feature_join_missing_rows":missing_rows,
        }
        if missing_rows:
            sample=p.loc[~complete,["symbol","as_of"]].head(20).to_dict(orient="records")
            raise LeadershipError(
                "M77.31 point-in-time feature parity failed after joining M77.21 authority; "
                f"missing_rows={missing_rows}, sample={sample}"
            )

    for c in ("px_ret_20","px_ret_60","px_ret_126","r_multiple"):
        p[c]=pd.to_numeric(p[c],errors="coerce").replace([np.inf,-np.inf],np.nan)

    # All ranks use only the same market-date candidate cross-section.
    p["rs20_rank"]=p.groupby("as_of")["px_ret_20"].rank(pct=True,method="average")
    p["rs60_rank"]=p.groupby("as_of")["px_ret_60"].rank(pct=True,method="average")
    p["rs126_rank"]=p.groupby("as_of")["px_ret_126"].rank(pct=True,method="average")

    p["persist_20_60"]=(p["rs20_rank"]+p["rs60_rank"])/2.0
    p["persist_20_60_126"]=(p["rs20_rank"]+p["rs60_rank"]+p["rs126_rank"])/3.0
    p["stable_20_60_126"]=p[["rs20_rank","rs60_rank","rs126_rank"]].min(axis=1)
    p["accel_20_vs_60"]=p["rs20_rank"]-p["rs60_rank"]

    p["calendar_year"]=p["as_of"].dt.year
    p["calendar_month"]=p["as_of"].dt.to_period("M").astype(str)

    sector_col=next((c for c in ("sector","gics_sector","sector_name","stock_sector") if c in p.columns),None)
    return p,{
        "rows":int(len(p)),
        "symbols":int(p["symbol"].nunique()),
        "first_as_of":p["as_of"].min().date().isoformat(),
        "last_as_of":p["as_of"].max().date().isoformat(),
        "sector_column":sector_col,
        "sector_relative_leadership_available":bool(sector_col),
        "consumed_2018_2026_rows_read":0,
        "input_sha256":_sha(path),
        **feature_join_meta,
    }

def _state_mask(p:pd.DataFrame,state:str)->pd.Series:
    if state=="RS20_TOP20": return p["rs20_rank"]>=TOP_Q
    if state=="RS60_TOP20": return p["rs60_rank"]>=TOP_Q
    if state=="RS126_TOP20": return p["rs126_rank"]>=TOP_Q
    if state=="PERSIST_20_60_TOP20": return p["persist_20_60"]>=TOP_Q
    if state=="PERSIST_20_60_126_TOP20": return p["persist_20_60_126"]>=TOP_Q
    if state=="STABLE_20_60_126_TOP20": return p["stable_20_60_126"]>=TOP_Q
    if state=="ACCEL_20_VS_60_TOP20":
        return p.groupby("as_of")["accel_20_vs_60"].rank(pct=True,method="average")>=TOP_Q
    if state=="DECEL_20_VS_60_BOTTOM20":
        return p.groupby("as_of")["accel_20_vs_60"].rank(pct=True,method="average")<=BOTTOM_Q
    raise KeyError(state)

def _paired_date_uplift(p:pd.DataFrame,mask:pd.Series)->dict[str,Any]:
    rows=[]
    for d,g in p.groupby("as_of"):
        m=mask.loc[g.index]
        a=g[m]
        b=g[~m]
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
    for state in LEADERSHIP_STATES:
        mask=_state_mask(p,state).fillna(False)
        selected=p[mask].copy()
        complement=p[~mask].copy()
        m=_metrics(selected); c=_metrics(complement); nm=_metrics(_nonoverlap(selected))
        paired=_paired_date_uplift(p,mask)
        rows.append({
            "state":state,**m,
            "baseline_mean_r":baseline.get("mean_r"),
            "baseline_profit_factor":baseline.get("profit_factor"),
            "complement_mean_r":c.get("mean_r"),
            "complement_profit_factor":c.get("profit_factor"),
            "mean_r_uplift_vs_full":m.get("mean_r",np.nan)-baseline.get("mean_r",np.nan),
            "mean_r_uplift_vs_complement":m.get("mean_r",np.nan)-c.get("mean_r",np.nan),
            "profit_factor_uplift_vs_complement":m.get("profit_factor",np.nan)-c.get("profit_factor",np.nan),
            "nonoverlap_n":nm.get("n",0),
            "nonoverlap_mean_r":nm.get("mean_r",np.nan),
            "nonoverlap_profit_factor":nm.get("profit_factor",np.nan),
            **paired,
        })
        for year,g in p.groupby("calendar_year"):
            ym=_state_mask(g,state).fillna(False)
            a=_metrics(g[ym]); b=_metrics(g[~ym])
            years.append({
                "state":state,"year":int(year),
                "selected_n":a.get("n",0),
                "mean_r":a.get("mean_r",np.nan),
                "mean_r_uplift_vs_complement":a.get("mean_r",np.nan)-b.get("mean_r",np.nan),
                "profit_factor":a.get("profit_factor",np.nan),
            })
        for month,g in p.groupby("calendar_month"):
            mm=_state_mask(g,state).fillna(False)
            a=_metrics(g[mm]); b=_metrics(g[~mm])
            months.append({
                "state":state,"month":month,
                "selected_n":a.get("n",0),
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
    out["development_ready_leadership_state"]=out[gates].all(axis=1)
    return out.sort_values(
        ["development_ready_leadership_state","mean_r_uplift_vs_complement","mean_r"],
        ascending=[False,False,False]
    ).reset_index(drop=True)

def run_lab(cfg:LeadershipConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir); outdir.mkdir(parents=True,exist_ok=True)
    p,meta=load_panel(cfg)
    evidence,years,months=evaluate_states(p)
    ready=build_readiness(evidence,years,months)

    evidence.to_csv(outdir/"relative_strength_leadership_evidence.csv",index=False)
    years.to_csv(outdir/"relative_strength_leadership_year_evidence.csv",index=False)
    months.to_csv(outdir/"relative_strength_leadership_month_evidence.csv",index=False)
    ready.to_csv(outdir/"relative_strength_leadership_readiness.csv",index=False)

    state_cols=[
        "symbol","as_of","entry_date","px_ret_20","px_ret_60","px_ret_126",
        "rs20_rank","rs60_rank","rs126_rank","persist_20_60","persist_20_60_126",
        "stable_20_60_126","accel_20_vs_60","r_multiple"
    ]
    p[state_cols].to_csv(outdir/"point_in_time_relative_strength_state_panel.csv.gz",index=False,compression="gzip")

    best=ready[ready["development_ready_leadership_state"]==True].head(1)
    report=[
        "# M77.31 Cross-Sectional Relative Strength Persistence & Leadership Edge Discovery","",
        "## Frozen research boundary","",
        "- Development evidence only through 2017-12-31.",
        "- Uses the frozen M77.26.1 executable NEXT_OPEN / 5ATR / 3ATR / 60-session cohort.",
        "- No M77.23 DRVE change.",
        "- PSVE / MGE / CQMI / CPRE prospective protocols are not read or modified.",
        "- No new PROBABILITY_UP threshold, Top-K, or management geometry is searched.",
        "- All relative-strength ranks are same-date point-in-time cross-sectional transforms.","",
        "## Readiness","",_md(ready),"",
        "## Year evidence","",_md(years,80),"",
    ]
    if not meta["sector_relative_leadership_available"]:
        report += [
            "## Sector-relative diagnostic","",
            "No point-in-time sector field exists in the frozen executable panel. "
            "Sector-relative leadership was therefore not fabricated or inferred.",""
        ]
    (outdir/"RELATIVE_STRENGTH_PERSISTENCE_LEADERSHIP_REPORT.md").write_text("\n".join(report))

    summary={
        "version":VERSION,
        "status":"COMPLETE",
        "completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31",
        "consumed_2018_2026_rows_read":0,
        "frozen_management_geometry":{"entry":"NEXT_OPEN","horizon":60,"target_atr":5.0,"stop_atr":3.0},
        "leadership_states_tested":list(LEADERSHIP_STATES),
        "fixed_top_quantile":TOP_Q,
        "fixed_bottom_quantile":BOTTOM_Q,
        "point_in_time_cross_sectional_ranks":True,
        "sector_relative_leadership_available":meta["sector_relative_leadership_available"],
        "sector_column":meta["sector_column"],
        "development_ready_leadership_states":int(ready["development_ready_leadership_state"].sum()),
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
        "next_step":"REVIEW DEVELOPMENT-ONLY LEADERSHIP/PERSISTENCE EVIDENCE; ANY SURVIVOR IS HYPOTHESIS-GENERATING AND REQUIRES SEPARATE PROSPECTIVE GOVERNANCE",
    }
    _atomic_json(outdir/"relative_strength_persistence_leadership_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{
        "version":VERSION,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "config":cfg.__dict__,
        "frozen_states":list(LEADERSHIP_STATES),
        "fixed_top_quantile":TOP_Q,
        "fixed_bottom_quantile":BOTTOM_Q,
        "upstream":meta,
        "forbidden_outcome_window":"2018-01-01 THROUGH 2026-12-31",
        "production_authority_effect":False,
    })
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.31 cross-sectional relative-strength persistence and leadership edge discovery")
    p.add_argument("--project-root",required=True)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    print(json.dumps(run_lab(LeadershipConfig(project_root=a.project_root)),indent=2,sort_keys=True,default=_json_default))
    return 0
