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

VERSION="M77.37.0-OUTCOME-ASYMMETRY-CONDITIONAL-TAIL-STRUCTURE-DISCOVERY-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
PRIMARY_HORIZON=60
PRIMARY_TARGET_ATR=5.0
PRIMARY_STOP_ATR=3.0
TOP_Q=0.80
BOTTOM_Q=0.20

# Frozen before Development outcome inspection.
CONDITION_STATES=(
    "PROBABILITY_UP_TOP20",
    "DRVE_RISK_LOWER20",
    "OVERALL_SCORE_TOP20",
    "IDI_TRADE_QUALITY_TOP20",
    "OPTIONS_SUITABILITY_TOP20",
    "PROBABILITY_UP_BOTTOM20",
    "DRVE_RISK_HIGHER20",
    "OVERALL_SCORE_BOTTOM20",
)

class TailStructureError(RuntimeError):
    pass

@dataclass(frozen=True)
class TailStructureConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    output_dir:str="research_data/m77_37/outcome_asymmetry_conditional_tail_structure_discovery"


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

def _metrics(g:pd.DataFrame)->dict[str,Any]:
    if g.empty:return {"n":0}
    r=pd.to_numeric(g["r_multiple"],errors="coerce").dropna()
    if r.empty:return {"n":0}
    x=g.loc[r.index].copy()
    pos=r[r>0]; neg=r[r<0]
    gp=float(pos.sum()); gl=float(-neg.sum())
    sym=x.assign(_r=r).groupby("symbol")["_r"].mean()
    contrib=x.assign(_r=r).groupby("symbol")["_r"].sum().abs().sort_values(ascending=False)
    denom=float(contrib.sum())
    mean_gain=float(pos.mean()) if len(pos) else np.nan
    mean_loss=float(-neg.mean()) if len(neg) else np.nan
    return {
        "n":int(len(r)),
        "symbols":int(x["symbol"].nunique()),
        "mean_r":float(r.mean()),
        "median_r":float(r.median()),
        "win_rate":float((r>0).mean()),
        "profit_factor":float(gp/gl) if gl>0 else np.inf,
        "p01_r":float(r.quantile(.01)),
        "p05_r":float(r.quantile(.05)),
        "p10_r":float(r.quantile(.10)),
        "p90_r":float(r.quantile(.90)),
        "p95_r":float(r.quantile(.95)),
        "p99_r":float(r.quantile(.99)),
        "loss_1r_rate":float((r<=-1.0).mean()),
        "loss_2r_rate":float((r<=-2.0).mean()),
        "gain_1r_rate":float((r>=1.0).mean()),
        "gain_2r_rate":float((r>=2.0).mean()),
        "mean_gain_r":mean_gain,
        "mean_loss_abs_r":mean_loss,
        "gain_loss_ratio":float(mean_gain/mean_loss) if mean_loss and np.isfinite(mean_loss) else np.nan,
        "right_left_tail_ratio_95_05":float(r.quantile(.95)/abs(r.quantile(.05))) if r.quantile(.05)<0 else np.nan,
        "equal_symbol_mean_r":float(sym.mean()) if len(sym) else np.nan,
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

def load_panel(cfg:TailStructureConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    ep=_resolve(root,cfg.executable_panel_path)
    if not ep.exists(): raise TailStructureError(f"Executable Development panel missing: {ep}")

    p=pd.read_csv(ep)
    p["as_of"]=pd.to_datetime(p["as_of"],errors="coerce")
    p["entry_date"]=pd.to_datetime(p["entry_date"],errors="coerce")
    p=p[
        (pd.to_numeric(p["horizon"],errors="coerce")==PRIMARY_HORIZON)
        &(pd.to_numeric(p["target_atr"],errors="coerce")==PRIMARY_TARGET_ATR)
        &(pd.to_numeric(p["stop_atr"],errors="coerce")==PRIMARY_STOP_ATR)
    ].copy()
    if p.empty: raise TailStructureError("Frozen executable cohort missing")
    if (p["as_of"]>DEVELOPMENT_END).any():
        raise TailStructureError("M77.37 refuses post-2017 evidence")

    required=(
        "symbol","as_of","r_multiple",
        "probability_up","bearish_rank_pct","overall_score",
        "idi_trade_quality","score_options_suitability",
    )
    missing=[c for c in required if c not in p.columns]
    if missing:
        raise TailStructureError(f"M77.26.1 executable authority missing required conditional-tail fields: {missing}")

    p["symbol"]=p["symbol"].astype(str).str.upper()
    for c in required[2:]:
        p[c]=pd.to_numeric(p[c],errors="coerce").replace([np.inf,-np.inf],np.nan)
    complete=p[list(required[3:])].notna().all(axis=1)
    if (~complete).any():
        detail=[]
        for _,row in p.loc[~complete,["symbol","as_of",*required[3:]]].head(20).iterrows():
            detail.append({
                "symbol":row["symbol"],"as_of":row["as_of"],
                "missing_fields":[c for c in required[3:] if pd.isna(row[c])]
            })
        raise TailStructureError(
            f"M77.37 candidate-condition parity failed; missing_rows={int((~complete).sum())}, sample={detail}"
        )

    # Same-date PIT ranks.
    p["rank_probability_up"]=p.groupby("as_of")["probability_up"].rank(pct=True,method="average")
    # Lower bearish_rank_pct = lower modeled downside risk.
    p["rank_drv_low_risk"]=1.0-p["bearish_rank_pct"]
    p["rank_overall_score"]=p.groupby("as_of")["overall_score"].rank(pct=True,method="average")
    p["rank_idi_trade_quality"]=p.groupby("as_of")["idi_trade_quality"].rank(pct=True,method="average")
    p["rank_options_suitability"]=p.groupby("as_of")["score_options_suitability"].rank(pct=True,method="average")
    p["calendar_year"]=p["as_of"].dt.year
    p["calendar_month"]=p["as_of"].dt.to_period("M").astype(str)

    return p,{
        "rows":int(len(p)),
        "symbols":int(p["symbol"].nunique()),
        "dates":int(p["as_of"].nunique()),
        "first_as_of":p["as_of"].min().date().isoformat(),
        "last_as_of":p["as_of"].max().date().isoformat(),
        "executable_input_sha256":_sha(ep),
        "condition_authority_source":"M77.26.1_EXECUTABLE_PANEL",
        "condition_authority_complete_rows":int(complete.sum()),
        "condition_authority_missing_rows":int((~complete).sum()),
        "consumed_2018_2026_rows_read":0,
    }

def _state_mask(p:pd.DataFrame,state:str)->pd.Series:
    if state=="PROBABILITY_UP_TOP20": return p["rank_probability_up"]>=TOP_Q
    if state=="DRVE_RISK_LOWER20": return p["rank_drv_low_risk"]>=TOP_Q
    if state=="OVERALL_SCORE_TOP20": return p["rank_overall_score"]>=TOP_Q
    if state=="IDI_TRADE_QUALITY_TOP20": return p["rank_idi_trade_quality"]>=TOP_Q
    if state=="OPTIONS_SUITABILITY_TOP20": return p["rank_options_suitability"]>=TOP_Q
    if state=="PROBABILITY_UP_BOTTOM20": return p["rank_probability_up"]<=BOTTOM_Q
    if state=="DRVE_RISK_HIGHER20": return p["rank_drv_low_risk"]<=BOTTOM_Q
    if state=="OVERALL_SCORE_BOTTOM20": return p["rank_overall_score"]<=BOTTOM_Q
    raise KeyError(state)

def evaluate_states(p:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    rows=[]; years=[]; months=[]
    baseline=_metrics(p)
    for state in CONDITION_STATES:
        mask=_state_mask(p,state).fillna(False)
        selected=p[mask].copy()
        complement=p[~mask].copy()
        m=_metrics(selected); c=_metrics(complement); nm=_metrics(_nonoverlap(selected))
        rows.append({
            "state":state,**m,
            "baseline_p05_r":baseline.get("p05_r"),
            "baseline_p95_r":baseline.get("p95_r"),
            "baseline_loss_1r_rate":baseline.get("loss_1r_rate"),
            "baseline_gain_loss_ratio":baseline.get("gain_loss_ratio"),
            "complement_p05_r":c.get("p05_r"),
            "complement_p95_r":c.get("p95_r"),
            "complement_loss_1r_rate":c.get("loss_1r_rate"),
            "complement_gain_loss_ratio":c.get("gain_loss_ratio"),
            "p05_improvement_vs_complement":m.get("p05_r",np.nan)-c.get("p05_r",np.nan),
            "p95_improvement_vs_complement":m.get("p95_r",np.nan)-c.get("p95_r",np.nan),
            "loss_1r_rate_reduction_vs_complement":c.get("loss_1r_rate",np.nan)-m.get("loss_1r_rate",np.nan),
            "loss_2r_rate_reduction_vs_complement":c.get("loss_2r_rate",np.nan)-m.get("loss_2r_rate",np.nan),
            "gain_loss_ratio_uplift_vs_complement":m.get("gain_loss_ratio",np.nan)-c.get("gain_loss_ratio",np.nan),
            "nonoverlap_n":nm.get("n",0),
            "nonoverlap_p05_r":nm.get("p05_r",np.nan),
            "nonoverlap_gain_loss_ratio":nm.get("gain_loss_ratio",np.nan),
            "nonoverlap_profit_factor":nm.get("profit_factor",np.nan),
        })
        for year,g in p.groupby("calendar_year"):
            mm=_state_mask(g,state).fillna(False)
            a=_metrics(g[mm]); b=_metrics(g[~mm])
            years.append({
                "state":state,"year":int(year),
                "selected_n":a.get("n",0),
                "p05_r":a.get("p05_r",np.nan),
                "loss_1r_rate":a.get("loss_1r_rate",np.nan),
                "gain_loss_ratio":a.get("gain_loss_ratio",np.nan),
                "p05_improvement_vs_complement":a.get("p05_r",np.nan)-b.get("p05_r",np.nan),
                "loss_1r_rate_reduction_vs_complement":b.get("loss_1r_rate",np.nan)-a.get("loss_1r_rate",np.nan),
            })
        for month,g in p.groupby("calendar_month"):
            mm=_state_mask(g,state).fillna(False)
            a=_metrics(g[mm]); b=_metrics(g[~mm])
            months.append({
                "state":state,"month":month,
                "selected_n":a.get("n",0),
                "p05_r":a.get("p05_r",np.nan),
                "gain_loss_ratio":a.get("gain_loss_ratio",np.nan),
                "loss_1r_rate_reduction_vs_complement":b.get("loss_1r_rate",np.nan)-a.get("loss_1r_rate",np.nan),
            })
    return pd.DataFrame(rows),pd.DataFrame(years),pd.DataFrame(months)

def build_readiness(evidence:pd.DataFrame,years:pd.DataFrame,months:pd.DataFrame)->pd.DataFrame:
    y=years.assign(
        positive=lambda x:(x["p05_improvement_vs_complement"]>=0)&(x["loss_1r_rate_reduction_vs_complement"]>=0)
    ).groupby("state")["positive"].agg(["sum","count"]).reset_index()
    y["positive_tail_year_fraction"]=y["sum"]/y["count"].replace(0,np.nan)

    mo=months.assign(
        positive=lambda x:(x["loss_1r_rate_reduction_vs_complement"]>=0)
    ).groupby("state")["positive"].agg(["sum","count"]).reset_index()
    mo["nonworse_tail_month_fraction"]=mo["sum"]/mo["count"].replace(0,np.nan)

    out=evidence.merge(
        y[["state","positive_tail_year_fraction"]],on="state",how="left"
    ).merge(
        mo[["state","nonworse_tail_month_fraction"]],on="state",how="left"
    )

    out["gate_n"]=out["n"]>=1000
    out["gate_symbols"]=out["symbols"]>=200
    out["gate_p05_improvement"]=out["p05_improvement_vs_complement"]>=0.10
    out["gate_loss1_reduction"]=out["loss_1r_rate_reduction_vs_complement"]>=0.01
    out["gate_gain_loss_ratio"]=out["gain_loss_ratio"]>=1.10
    out["gate_gain_loss_uplift"]=out["gain_loss_ratio_uplift_vs_complement"]>=0.05
    out["gate_right_left_tail_ratio"]=out["right_left_tail_ratio_95_05"]>=1.0
    out["gate_nonoverlap_p05"]=out["nonoverlap_p05_r"]>=-2.5
    out["gate_nonoverlap_gain_loss"]=out["nonoverlap_gain_loss_ratio"]>=1.05
    out["gate_positive_tail_years"]=out["positive_tail_year_fraction"]>=0.70
    out["gate_nonworse_tail_months"]=out["nonworse_tail_month_fraction"]>=0.60
    out["gate_concentration"]=out["top10_abs_contribution_fraction"]<=0.25
    gates=[c for c in out.columns if c.startswith("gate_")]
    out["development_ready_tail_state"]=out[gates].all(axis=1)
    return out.sort_values(
        ["development_ready_tail_state","loss_1r_rate_reduction_vs_complement","p05_improvement_vs_complement"],
        ascending=[False,False,False]
    ).reset_index(drop=True)

def run_lab(cfg:TailStructureConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    p,meta=load_panel(cfg)
    evidence,years,months=evaluate_states(p)
    ready=build_readiness(evidence,years,months)

    evidence.to_csv(outdir/"conditional_tail_structure_evidence.csv",index=False)
    years.to_csv(outdir/"conditional_tail_structure_year_evidence.csv",index=False)
    months.to_csv(outdir/"conditional_tail_structure_month_evidence.csv",index=False)
    ready.to_csv(outdir/"conditional_tail_structure_readiness.csv",index=False)

    p[[
        "symbol","as_of","entry_date","probability_up","bearish_rank_pct","overall_score",
        "idi_trade_quality","score_options_suitability",
        "rank_probability_up","rank_drv_low_risk","rank_overall_score",
        "rank_idi_trade_quality","rank_options_suitability","r_multiple"
    ]].to_csv(outdir/"point_in_time_conditional_tail_panel.csv.gz",index=False,compression="gzip")

    best=ready[ready["development_ready_tail_state"]==True].head(1)
    summary={
        "version":VERSION,"status":"COMPLETE",
        "completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31",
        "consumed_2018_2026_rows_read":0,
        "frozen_management_geometry":{"entry":"NEXT_OPEN","horizon":60,"target_atr":5.0,"stop_atr":3.0},
        "condition_states_tested":list(CONDITION_STATES),
        "objective":"PAYOFF_ASYMMETRY_AND_LEFT_TAIL_IMPROVEMENT",
        "development_ready_tail_states":int(ready["development_ready_tail_state"].sum()),
        "highest_ranked_development_ready_state":(
            best.iloc[0][[
                "state","n","symbols","p05_r","p95_r","loss_1r_rate","loss_2r_rate",
                "gain_loss_ratio","right_left_tail_ratio_95_05",
                "p05_improvement_vs_complement","loss_1r_rate_reduction_vs_complement",
                "gain_loss_ratio_uplift_vs_complement","nonoverlap_p05_r",
                "nonoverlap_gain_loss_ratio","positive_tail_year_fraction",
                "nonworse_tail_month_fraction","top10_abs_contribution_fraction"
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
        "next_step":"REVIEW DEVELOPMENT-ONLY CONDITIONAL TAIL/ASYMMETRY EVIDENCE; ANY SURVIVOR IS HYPOTHESIS-GENERATING AND REQUIRES SEPARATE PROSPECTIVE GOVERNANCE",
    }
    _atomic_json(outdir/"outcome_asymmetry_conditional_tail_structure_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{
        "version":VERSION,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "config":cfg.__dict__,
        "frozen_condition_states":list(CONDITION_STATES),
        "objective":"PAYOFF_ASYMMETRY_AND_LEFT_TAIL_IMPROVEMENT",
        "forbidden_outcome_window":"2018-01-01 THROUGH 2026-12-31",
        "upstream":meta,
        "production_authority_effect":False,
    })

    report=[
        "# M77.37 Outcome Asymmetry & Conditional Tail Structure Discovery","",
        "Development-only conditional tail analysis under frozen NEXT_OPEN / 5ATR / 3ATR / 60-session execution.","",
        "Primary objective: left-tail reduction and payoff asymmetry, not average-return optimization.","",
        "## Readiness","",
        ready.to_string(index=False),"",
    ]
    (outdir/"OUTCOME_ASYMMETRY_CONDITIONAL_TAIL_STRUCTURE_REPORT.md").write_text("\n".join(report))
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.37 outcome asymmetry and conditional tail structure discovery")
    p.add_argument("--project-root",required=True)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    print(json.dumps(run_lab(TailStructureConfig(project_root=a.project_root)),indent=2,sort_keys=True,default=_json_default))
    return 0
