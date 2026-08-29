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

VERSION="M77.27.0-CANDIDATE-QUALITY-MANAGEMENT-INTERACTION-EDGE-DISCOVERY-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
PRIMARY_HORIZON=60
PRIMARY_TARGET_ATR=5.0
PRIMARY_STOP_ATR=3.0

FIXED_STATES=(
    "PROBABILITY_UP_TOP20",
    "PROBABILITY_UP_BOTTOM20",
    "DRVE_RISK_LOWER_HALF",
    "DRVE_RISK_HIGHER_DECILE",
    "OVERALL_QUALITY_TOP25",
    "OVERALL_QUALITY_BOTTOM25",
    "IDI_TRADE_QUALITY_TOP25",
    "IDI_TRADE_QUALITY_BOTTOM25",
    "OPTIONS_SUITABILITY_TOP25",
    "OPTIONS_SUITABILITY_BOTTOM25",
    "ATR_PCT_HIGH",
    "ATR_PCT_LOW",
    "ABOVE_SMA20",
    "BELOW_SMA20",
    "MOM5_POSITIVE",
    "MOM5_NONPOSITIVE",
)

class InteractionError(RuntimeError): pass

@dataclass(frozen=True)
class InteractionConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    timing_panel_path:str="research_data/m77_25/entry_timing_path_dependent_edge_discovery/entry_timing_observation_panel.csv.gz"
    output_dir:str="research_data/m77_27/candidate_quality_management_interaction_edge_discovery"


def _resolve(root:Path,raw:str)->Path:
    p=Path(raw).expanduser()
    return p if p.is_absolute() else root/p

def _json_default(v:Any)->Any:
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.floating,)):return None if not np.isfinite(v) else float(v)
    if isinstance(v,(pd.Timestamp,datetime)):return v.isoformat()
    if isinstance(v,Path):return str(v)
    raise TypeError(type(v).__name__)

def _sha(path:Path)->str:
    import hashlib
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def _atomic_json(path:Path,payload:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True,default=_json_default))
    os.replace(tmp,path)

def _md(df:pd.DataFrame,n:int=30)->str:
    if df.empty:return "_No rows._"
    x=df.head(n);cols=[str(c) for c in x.columns]
    def f(v):
        if pd.isna(v):return ""
        if isinstance(v,(float,np.floating)):return f"{float(v):.6g}"
        return str(v).replace("|","\\|").replace("\n"," ")
    lines=["| "+" | ".join(cols)+" |","| "+" | ".join("---" for _ in cols)+" |"]
    for _,r in x.iterrows():lines.append("| "+" | ".join(f(r[c]) for c in x.columns)+" |")
    return "\n".join(lines)

def load_primary_panel(cfg:InteractionConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    ep=_resolve(root,cfg.executable_panel_path)
    tp=_resolve(root,cfg.timing_panel_path)
    for p in (ep,tp):
        if not p.exists():raise InteractionError(f"Required Development evidence missing: {p}")

    e=pd.read_csv(ep)
    e["as_of"]=pd.to_datetime(e["as_of"],errors="coerce")
    e=e[
        (e["horizon"]==PRIMARY_HORIZON)
        &(e["target_atr"]==PRIMARY_TARGET_ATR)
        &(e["stop_atr"]==PRIMARY_STOP_ATR)
    ].copy()
    if e.empty:raise InteractionError("Frozen 60d/5ATR/3ATR executable cohort missing")
    if (e["as_of"]>DEVELOPMENT_END).any():raise InteractionError("M77.27 refuses post-2017 executable evidence")

    # M77.25 contains candidate-date path-state fields. NEXT_OPEN rows are duplicated
    # by horizon; take one deterministic candidate-date row.
    usecols=["symbol","as_of","policy","px_ret_5","dist_sma_20","rsi_14","atr_pct_14"]
    t=pd.read_csv(tp,usecols=lambda c:c in usecols)
    t["as_of"]=pd.to_datetime(t["as_of"],errors="coerce")
    t=t[t["policy"]=="NEXT_OPEN"].drop_duplicates(["symbol","as_of"],keep="first")
    if (t["as_of"]>DEVELOPMENT_END).any():raise InteractionError("M77.27 refuses post-2017 timing evidence")

    panel=e.merge(
        t[["symbol","as_of","px_ret_5","dist_sma_20","rsi_14","atr_pct_14"]],
        on=["symbol","as_of"],how="left",validate="many_to_one"
    )
    panel["calendar_year"]=panel["as_of"].dt.year

    # All percentile/rank states are contemporaneous, preventing look-ahead.
    for c in ("probability_up","overall_score","idi_trade_quality","score_options_suitability","atr_pct_14"):
        panel[c]=pd.to_numeric(panel.get(c),errors="coerce")
        panel[f"rank_{c}"]=panel.groupby("as_of")[c].rank(method="average",pct=True)
    panel["bearish_rank_pct"]=pd.to_numeric(panel["bearish_rank_pct"],errors="coerce")
    panel["px_ret_5"]=pd.to_numeric(panel["px_ret_5"],errors="coerce")
    panel["dist_sma_20"]=pd.to_numeric(panel["dist_sma_20"],errors="coerce")

    return panel,{
        "executable_panel_sha256":_sha(ep),
        "timing_panel_sha256":_sha(tp),
        "rows":int(len(panel)),
        "symbols":int(panel["symbol"].nunique()),
        "first_as_of":panel["as_of"].min().date().isoformat(),
        "last_as_of":panel["as_of"].max().date().isoformat(),
        "consumed_2018_2026_rows_read":0,
    }

def _state_mask(p:pd.DataFrame,state:str)->pd.Series:
    if state=="PROBABILITY_UP_TOP20":return p["rank_probability_up"]>=0.80
    if state=="PROBABILITY_UP_BOTTOM20":return p["rank_probability_up"]<=0.20
    if state=="DRVE_RISK_LOWER_HALF":return p["bearish_rank_pct"]>=0.50
    if state=="DRVE_RISK_HIGHER_DECILE":return p["bearish_rank_pct"]<=0.10
    if state=="OVERALL_QUALITY_TOP25":return p["rank_overall_score"]>=0.75
    if state=="OVERALL_QUALITY_BOTTOM25":return p["rank_overall_score"]<=0.25
    if state=="IDI_TRADE_QUALITY_TOP25":return p["rank_idi_trade_quality"]>=0.75
    if state=="IDI_TRADE_QUALITY_BOTTOM25":return p["rank_idi_trade_quality"]<=0.25
    if state=="OPTIONS_SUITABILITY_TOP25":return p["rank_score_options_suitability"]>=0.75
    if state=="OPTIONS_SUITABILITY_BOTTOM25":return p["rank_score_options_suitability"]<=0.25
    if state=="ATR_PCT_HIGH":return p["rank_atr_pct_14"]>=0.75
    if state=="ATR_PCT_LOW":return p["rank_atr_pct_14"]<=0.25
    if state=="ABOVE_SMA20":return p["dist_sma_20"]>0
    if state=="BELOW_SMA20":return p["dist_sma_20"]<=0
    if state=="MOM5_POSITIVE":return p["px_ret_5"]>0
    if state=="MOM5_NONPOSITIVE":return p["px_ret_5"]<=0
    raise InteractionError(f"Unknown state {state}")

def _metrics(g:pd.DataFrame)->dict[str,Any]:
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
        "gap_stop_fraction":float(x["exit_type"].eq("STOP_GAP").mean()),
        "tail_1pct_r":float(r.quantile(.01)),
        "top10_abs_contribution_fraction":float(contrib.head(10).sum()/denom) if denom>0 else np.nan,
    }

def _nonoverlap(g:pd.DataFrame)->pd.DataFrame:
    keep=[]
    for _,sg in g.sort_values(["symbol","entry_date"]).groupby("symbol",sort=False):
        last=None
        for idx,row in sg.iterrows():
            d=pd.Timestamp(row["entry_date"])
            if last is None or (d-last).days>=84:
                keep.append(idx);last=d
    return g.loc[keep]

def interaction_evidence(panel:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    base=_metrics(panel)
    rows=[];years=[];non=[]
    for state in FIXED_STATES:
        mask=_state_mask(panel,state).fillna(False)
        a=panel[mask].copy();b=panel[~mask].copy()
        am=_metrics(a);bm=_metrics(b)
        an=_metrics(_nonoverlap(a)) if not a.empty else {"n":0}
        row={
            "state":state,
            "state_fraction":float(mask.mean()),
            **{f"state_{k}":v for k,v in am.items()},
            **{f"complement_{k}":v for k,v in bm.items()},
            "full_mean_r":base.get("mean_r"),
            "interaction_mean_r_uplift":am.get("mean_r",np.nan)-bm.get("mean_r",np.nan),
            "interaction_profit_factor_uplift":am.get("profit_factor",np.nan)-bm.get("profit_factor",np.nan),
            "interaction_win_rate_uplift":am.get("win_rate",np.nan)-bm.get("win_rate",np.nan),
            "nonoverlap_state_mean_r":an.get("mean_r"),
            "nonoverlap_state_profit_factor":an.get("profit_factor"),
        }
        rows.append(row)
        for year,yg in panel.groupby("calendar_year"):
            ym=_state_mask(yg,state).fillna(False)
            ya=_metrics(yg[ym]);yb=_metrics(yg[~ym])
            years.append({
                "state":state,"year":int(year),
                "state_n":ya.get("n",0),"complement_n":yb.get("n",0),
                "interaction_mean_r_uplift":ya.get("mean_r",np.nan)-yb.get("mean_r",np.nan),
                "interaction_profit_factor_uplift":ya.get("profit_factor",np.nan)-yb.get("profit_factor",np.nan),
            })
        non.append({"state":state,**an})
    return pd.DataFrame(rows),pd.DataFrame(years),pd.DataFrame(non)

def readiness(evidence:pd.DataFrame,years:pd.DataFrame)->pd.DataFrame:
    y=years.assign(
        positive=lambda x:(x["interaction_mean_r_uplift"]>0)&(x["interaction_profit_factor_uplift"]>0)
    ).groupby("state")["positive"].agg(["sum","count"]).reset_index()
    y["positive_year_fraction"]=y["sum"]/y["count"].replace(0,np.nan)
    out=evidence.merge(y[["state","positive_year_fraction"]],on="state",how="left")
    out["gate_state_n"]=out["state_n"]>=1500
    out["gate_symbols"]=out["state_symbols"]>=250
    out["gate_mean_r"]=out["state_mean_r"]>=0.15
    out["gate_interaction_uplift"]=out["interaction_mean_r_uplift"]>=0.075
    out["gate_pf"]=out["state_profit_factor"]>=1.30
    out["gate_pf_uplift"]=out["interaction_profit_factor_uplift"]>=0.15
    out["gate_equal_symbol"]=out["state_equal_symbol_mean_r"]>=0.12
    out["gate_positive_symbols"]=out["state_positive_symbol_fraction"]>=0.65
    out["gate_nonoverlap"]=out["nonoverlap_state_mean_r"]>=0.12
    out["gate_nonoverlap_pf"]=out["nonoverlap_state_profit_factor"]>=1.25
    out["gate_year_stability"]=out["positive_year_fraction"]>=0.70
    out["gate_concentration"]=out["state_top10_abs_contribution_fraction"]<=0.25
    out["gate_gap"]=out["state_gap_stop_fraction"]<=0.10
    out["gate_tail"]=out["state_tail_1pct_r"]>=-2.50
    gates=[c for c in out.columns if c.startswith("gate_")]
    out["development_ready_interaction"]=out[gates].all(axis=1)
    return out.sort_values(
        ["development_ready_interaction","interaction_mean_r_uplift","state_mean_r"],
        ascending=[False,False,False]
    ).reset_index(drop=True)

def run_lab(cfg:InteractionConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    panel,meta=load_primary_panel(cfg)
    evidence,years,non=interaction_evidence(panel)
    ready=readiness(evidence,years)

    evidence.to_csv(outdir/"candidate_quality_management_interaction_evidence.csv",index=False)
    years.to_csv(outdir/"candidate_quality_management_interaction_year_evidence.csv",index=False)
    non.to_csv(outdir/"candidate_quality_management_interaction_nonoverlap.csv",index=False)
    ready.to_csv(outdir/"candidate_quality_management_interaction_readiness.csv",index=False)

    report=[
        "# M77.27 Candidate Quality × Management Interaction Edge Discovery","",
        "## Frozen base management","",
        "- NEXT_OPEN entry.",
        "- 5 ATR target / 3 ATR stop.",
        "- 60 trading-session maximum hold.",
        "- Full-cohort executable R from M77.26.1.",
        "- No geometry retuning and no 2018-2026 outcomes.","",
        "## Development-ready interactions","",_md(ready[ready["development_ready_interaction"]==True]),"",
        "## Highest interaction uplifts","",_md(ready.head(25)),"",
    ]
    (outdir/"CANDIDATE_QUALITY_MANAGEMENT_INTERACTION_REPORT.md").write_text("\n".join(report))

    summary={
        "version":VERSION,"status":"COMPLETE","completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31","consumed_2018_2026_rows_read":0,
        "frozen_management_geometry":{"horizon":60,"target_atr":5.0,"stop_atr":3.0,"entry":"NEXT_OPEN"},
        "fixed_states_tested":list(FIXED_STATES),
        "interaction_tests":int(len(evidence)),
        "development_ready_interactions":int(ready["development_ready_interaction"].sum()),
        "primary_panel_rows":int(len(panel)),"primary_symbols":int(panel["symbol"].nunique()),
        "m77_23_drv_modified":False,"m77_24_1_psve_modified":False,"m77_26_2_mge_modified":False,
        "production_authority_effect":False,"polygon_api_called":False,
        "next_step":"REVIEW DEVELOPMENT-ONLY INTERACTIONS; ANY SURVIVOR IS HYPOTHESIS-GENERATING AND REQUIRES A NEW PROSPECTIVE PROTOCOL",
        "upstream_sha256":meta,
    }
    _atomic_json(outdir/"candidate_quality_management_interaction_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{"version":VERSION,"config":cfg.__dict__,"summary":summary})
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.27 Development-only candidate-quality x management interaction discovery")
    p.add_argument("--project-root",required=True)
    p.add_argument("--executable-panel-path",default=InteractionConfig.executable_panel_path)
    p.add_argument("--timing-panel-path",default=InteractionConfig.timing_panel_path)
    p.add_argument("--output-dir",default=InteractionConfig.output_dir)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    cfg=InteractionConfig(
        project_root=a.project_root,executable_panel_path=a.executable_panel_path,
        timing_panel_path=a.timing_panel_path,output_dir=a.output_dir
    )
    print(json.dumps(run_lab(cfg),indent=2,sort_keys=True,default=_json_default))
    return 0
