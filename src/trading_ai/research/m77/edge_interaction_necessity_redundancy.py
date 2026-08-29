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

VERSION="M77.38.0-EDGE-INTERACTION-NECESSITY-REDUNDANCY-DECOMPOSITION-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")

CERT_HORIZON=60
CERT_STOP_ATR=3.0
CERT_TARGET_ATR=5.0

# Frozen neutral management counterfactual; chosen before Development outcome inspection.
NEUTRAL_HORIZON=60
NEUTRAL_STOP_ATR=3.0
NEUTRAL_TARGET_ATR=3.0

PROB_TOP_FRACTION=0.20
CAPITAL_TOP_K=3

class EdgeDecompositionError(RuntimeError):
    pass

@dataclass(frozen=True)
class EdgeDecompositionConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    output_dir:str="research_data/m77_38/edge_interaction_necessity_redundancy_decomposition"


def _resolve(root:Path,raw:str)->Path:
    p=Path(raw).expanduser()
    return p if p.is_absolute() else root/p

def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

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

def _metrics(g:pd.DataFrame)->dict[str,Any]:
    if g.empty:return {"n":0}
    r=pd.to_numeric(g["r_multiple"],errors="coerce").dropna()
    if r.empty:return {"n":0}
    x=g.loc[r.index].copy()
    pos=r[r>0];neg=r[r<0]
    gp=float(pos.sum());gl=float(-neg.sum())
    sym=x.assign(_r=r).groupby("symbol")["_r"].mean()
    return {
        "n":int(len(r)),
        "symbols":int(x["symbol"].nunique()),
        "dates":int(x["as_of"].nunique()),
        "mean_r":float(r.mean()),
        "median_r":float(r.median()),
        "win_rate":float((r>0).mean()),
        "profit_factor":float(gp/gl) if gl>0 else np.inf,
        "p05_r":float(r.quantile(.05)),
        "p95_r":float(r.quantile(.95)),
        "loss_1r_rate":float((r<=-1.0).mean()),
        "loss_2r_rate":float((r<=-2.0).mean()),
        "gain_1r_rate":float((r>=1.0).mean()),
        "gain_2r_rate":float((r>=2.0).mean()),
        "equal_symbol_mean_r":float(sym.mean()) if len(sym) else np.nan,
    }

def _nonoverlap(g:pd.DataFrame)->pd.DataFrame:
    if g.empty:return g
    z=g.sort_values(["symbol","entry_date","as_of"]).copy()
    keep=[];last_exit={}
    for idx,row in z.iterrows():
        sym=str(row["symbol"]);entry=pd.Timestamp(row["entry_date"])
        prev=last_exit.get(sym)
        if prev is not None and entry<=prev:continue
        keep.append(idx)
        exit_day=max(1,int(float(row.get("exit_day",CERT_HORIZON))))
        last_exit[sym]=entry+pd.offsets.BDay(exit_day)
    return z.loc[keep].copy()

def _delta(a:dict[str,Any],b:dict[str,Any])->dict[str,Any]:
    fields=("mean_r","win_rate","profit_factor","p05_r","p95_r","loss_1r_rate","loss_2r_rate","gain_1r_rate","gain_2r_rate","equal_symbol_mean_r")
    out={}
    for f in fields:
        av=a.get(f,np.nan);bv=b.get(f,np.nan)
        out[f"delta_{f}"]=float(av-bv) if np.isfinite(av) and np.isfinite(bv) else np.nan
    return out

def load_authority(cfg:EdgeDecompositionConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    ep=_resolve(root,cfg.executable_panel_path)
    if not ep.exists():raise EdgeDecompositionError(f"M77.26.1 executable authority missing: {ep}")
    p=pd.read_csv(ep)
    for c in ("as_of","entry_date"):
        p[c]=pd.to_datetime(p[c],errors="coerce")
    if (p["as_of"]>DEVELOPMENT_END).any():
        raise EdgeDecompositionError("M77.38 refuses post-2017 executable evidence")
    required=(
        "symbol","as_of","entry_date","horizon","stop_atr","target_atr","r_multiple",
        "probability_up","bearish_rank_pct","overall_score","idi_trade_quality",
        "score_options_suitability",
    )
    missing=[c for c in required if c not in p.columns]
    if missing:raise EdgeDecompositionError(f"M77.26.1 executable authority missing required columns: {missing}")
    p["symbol"]=p["symbol"].astype(str).str.upper()
    for c in ("horizon","stop_atr","target_atr","r_multiple","probability_up","bearish_rank_pct","overall_score","idi_trade_quality","score_options_suitability"):
        p[c]=pd.to_numeric(p[c],errors="coerce").replace([np.inf,-np.inf],np.nan)
    condition_complete=p[["probability_up","bearish_rank_pct","overall_score","idi_trade_quality","score_options_suitability"]].notna().all(axis=1)
    if (~condition_complete).any():
        raise EdgeDecompositionError(f"M77.38 candidate authority incomplete for {int((~condition_complete).sum())} rows")
    return p,{
        "rows":int(len(p)),
        "symbols":int(p["symbol"].nunique()),
        "dates":int(p["as_of"].nunique()),
        "first_as_of":p["as_of"].min().date().isoformat(),
        "last_as_of":p["as_of"].max().date().isoformat(),
        "executable_input_sha256":_sha(ep),
        "consumed_2018_2026_rows_read":0,
    }

def _geometry(p:pd.DataFrame,target:float,stop:float,horizon:int)->pd.DataFrame:
    x=p[
        (p["horizon"]==horizon)&(p["stop_atr"]==stop)&(p["target_atr"]==target)
    ].copy()
    if x.empty:
        raise EdgeDecompositionError(f"Frozen geometry unavailable: target={target}, stop={stop}, horizon={horizon}")
    dup=x.duplicated(["symbol","as_of"],keep=False)
    if dup.any():
        raise EdgeDecompositionError("Executable geometry is not unique on (symbol, as_of)")
    return x

def add_selection_states(x:pd.DataFrame)->pd.DataFrame:
    x=x.copy()
    x["probability_rank"]=x.groupby("as_of")["probability_up"].rank(ascending=False,method="first")
    x["cohort_n"]=x.groupby("as_of")["symbol"].transform("count")
    x["probability_pct_rank"]=x.groupby("as_of")["probability_up"].rank(pct=True,method="average")
    x["prob_top20"]=x["probability_pct_rank"]>=1.0-PROB_TOP_FRACTION
    x["capital_top3"]=x["probability_rank"]<=CAPITAL_TOP_K
    # CPRE top-3 is structurally derived from PROBABILITY_UP, so this is expected to be a subset.
    x["full_stack_proxy"]=x["capital_top3"]
    return x

def selection_decomposition(cert:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    x=add_selection_states(cert)
    cohorts={
        "POST_DRVE_BASELINE":x,
        "PROBABILITY_UP_TOP20":x[x["prob_top20"]],
        "CAPITAL_PRIORITY_TOP3":x[x["capital_top3"]],
        "FULL_STACK_PROXY_TOP3":x[x["full_stack_proxy"]],
        "PROB_TOP20_EXCLUDING_TOP3":x[x["prob_top20"]&~x["capital_top3"]],
        "COMPLEMENT_NOT_PROB_TOP20":x[~x["prob_top20"]],
    }
    base=_metrics(cohorts["POST_DRVE_BASELINE"])
    rows=[]
    for name,g in cohorts.items():
        m=_metrics(g);nm=_metrics(_nonoverlap(g))
        rows.append({
            "cohort":name,**m,
            **_delta(m,base),
            "nonoverlap_n":nm.get("n",0),
            "nonoverlap_mean_r":nm.get("mean_r",np.nan),
            "nonoverlap_profit_factor":nm.get("profit_factor",np.nan),
            "nonoverlap_p05_r":nm.get("p05_r",np.nan),
        })
    # Structural redundancy/overlap.
    a=x["prob_top20"];b=x["capital_top3"]
    both=int((a&b).sum());union=int((a|b).sum())
    redundancy=pd.DataFrame([
        {
            "pair":"PROBABILITY_UP_TOP20__VS__CAPITAL_PRIORITY_TOP3",
            "left_n":int(a.sum()),"right_n":int(b.sum()),
            "intersection_n":both,
            "jaccard":float(both/union) if union else np.nan,
            "right_subset_of_left":bool((~a[b]).sum()==0),
            "same_selection_fraction":float((a==b).mean()),
        }
    ])
    return pd.DataFrame(rows),redundancy

def management_decomposition(p:pd.DataFrame,cert:pd.DataFrame)->pd.DataFrame:
    neutral=_geometry(p,NEUTRAL_TARGET_ATR,NEUTRAL_STOP_ATR,NEUTRAL_HORIZON)
    # exact candidate matching.
    keys=["symbol","as_of"]
    a=cert[keys+["r_multiple","entry_date","exit_day","probability_up"]].rename(columns={
        "r_multiple":"cert_r","entry_date":"cert_entry_date","exit_day":"cert_exit_day"
    })
    b=neutral[keys+["r_multiple","entry_date","exit_day"]].rename(columns={
        "r_multiple":"neutral_r","entry_date":"neutral_entry_date","exit_day":"neutral_exit_day"
    })
    m=a.merge(b,on=keys,how="inner",validate="one_to_one")
    if m.empty:raise EdgeDecompositionError("No matched candidate observations across certified and neutral geometries")
    rows=[]
    # Build selection masks on matched authority without tuning.
    m["probability_pct_rank"]=m.groupby("as_of")["probability_up"].rank(pct=True,method="average")
    m["prob_top20"]=m["probability_pct_rank"]>=1.0-PROB_TOP_FRACTION
    m["probability_rank"]=m.groupby("as_of")["probability_up"].rank(ascending=False,method="first")
    m["capital_top3"]=m["probability_rank"]<=CAPITAL_TOP_K
    for label,sub in (
        ("ALL_MATCHED",m),
        ("PROBABILITY_UP_TOP20",m[m["prob_top20"]]),
        ("CAPITAL_PRIORITY_TOP3",m[m["capital_top3"]]),
    ):
        if sub.empty:continue
        diff=sub["cert_r"]-sub["neutral_r"]
        rows.append({
            "cohort":label,
            "matched_n":int(len(sub)),
            "symbols":int(sub["symbol"].nunique()),
            "certified_mean_r":float(sub["cert_r"].mean()),
            "neutral_3x3_mean_r":float(sub["neutral_r"].mean()),
            "management_mean_r_delta":float(diff.mean()),
            "management_median_r_delta":float(diff.median()),
            "certified_better_fraction":float((diff>0).mean()),
            "certified_worse_fraction":float((diff<0).mean()),
            "same_fraction":float((diff==0).mean()),
            "delta_p05":float(diff.quantile(.05)),
            "delta_p95":float(diff.quantile(.95)),
        })
    return pd.DataFrame(rows)

def attribution_summary(selection:pd.DataFrame,management:pd.DataFrame,redundancy:pd.DataFrame)->dict[str,Any]:
    s=selection.set_index("cohort")
    out={
        "drve_necessity_identifiable":False,
        "drve_necessity_reason":"M77.26.1 executable authority is conditioned on the post-DRVE candidate population; no pre-DRVE executable counterfactual is present.",
        "probability_up_incremental_mean_r_vs_post_drv_baseline":float(s.loc["PROBABILITY_UP_TOP20","delta_mean_r"]),
        "capital_top3_incremental_mean_r_vs_post_drv_baseline":float(s.loc["CAPITAL_PRIORITY_TOP3","delta_mean_r"]),
        "capital_top3_incremental_mean_r_vs_prob_top20":float(
            s.loc["CAPITAL_PRIORITY_TOP3","mean_r"]-s.loc["PROBABILITY_UP_TOP20","mean_r"]
        ),
        "cpre_structurally_dependent_on_probability_up":bool(redundancy.iloc[0]["right_subset_of_left"]),
    }
    if not management.empty:
        ma=management.set_index("cohort")
        out["certified_management_delta_all_matched"]=float(ma.loc["ALL_MATCHED","management_mean_r_delta"])
        out["certified_management_delta_prob_top20"]=float(ma.loc["PROBABILITY_UP_TOP20","management_mean_r_delta"])
        out["certified_management_delta_top3"]=float(ma.loc["CAPITAL_PRIORITY_TOP3","management_mean_r_delta"])
    return out

def run_lab(cfg:EdgeDecompositionConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    p,meta=load_authority(cfg)
    cert=_geometry(p,CERT_TARGET_ATR,CERT_STOP_ATR,CERT_HORIZON)
    selection,redundancy=selection_decomposition(cert)
    management=management_decomposition(p,cert)
    attribution=attribution_summary(selection,management,redundancy)

    selection.to_csv(outdir/"selection_necessity_decomposition.csv",index=False)
    management.to_csv(outdir/"management_geometry_matched_counterfactual.csv",index=False)
    redundancy.to_csv(outdir/"selection_redundancy_overlap.csv",index=False)

    summary={
        "version":VERSION,
        "status":"COMPLETE",
        "completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31",
        "consumed_2018_2026_rows_read":0,
        "scope":"POST_DRVE_EXECUTABLE_NECESSITY_AND_REDUNDANCY_DECOMPOSITION",
        "certified_management_geometry":{"entry":"NEXT_OPEN","horizon":60,"stop_atr":3.0,"target_atr":5.0},
        "neutral_management_counterfactual":{"entry":"NEXT_OPEN","horizon":60,"stop_atr":3.0,"target_atr":3.0},
        "probability_top_fraction":PROB_TOP_FRACTION,
        "capital_priority_top_k":CAPITAL_TOP_K,
        "drve_necessity_identifiable":False,
        "drve_necessity_reason":attribution["drve_necessity_reason"],
        "selection_cohorts":selection["cohort"].tolist(),
        "attribution":attribution,
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
        "next_step":"REVIEW POST-DRVE NECESSITY/REDUNDANCY DECOMPOSITION; DO NOT INFER DRVE INCREMENTAL CONTRIBUTION WITHOUT PRE-DRVE EXECUTABLE COUNTERFACTUAL AUTHORITY",
    }
    _atomic_json(outdir/"edge_interaction_necessity_redundancy_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{
        "version":VERSION,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "config":cfg.__dict__,
        "certified_geometry":summary["certified_management_geometry"],
        "neutral_counterfactual":summary["neutral_management_counterfactual"],
        "probability_top_fraction":PROB_TOP_FRACTION,
        "capital_priority_top_k":CAPITAL_TOP_K,
        "forbidden_outcome_window":"2018-01-01 THROUGH 2026-12-31",
        "drve_necessity_identifiable":False,
        "production_authority_effect":False,
        "upstream":meta,
    })

    report=[
        "# M77.38 Edge Interaction Necessity & Redundancy Decomposition","",
        "## Critical identifiability constraint","",
        attribution["drve_necessity_reason"],"",
        "## Selection decomposition","",selection.to_string(index=False),"",
        "## Management matched counterfactual","",management.to_string(index=False),"",
        "## Structural redundancy","",redundancy.to_string(index=False),"",
        "## Attribution summary","",json.dumps(attribution,indent=2,sort_keys=True,default=_json_default),
    ]
    (outdir/"EDGE_INTERACTION_NECESSITY_REDUNDANCY_REPORT.md").write_text("\n".join(report))
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.38 edge interaction necessity and redundancy decomposition")
    p.add_argument("--project-root",required=True)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    print(json.dumps(run_lab(EdgeDecompositionConfig(project_root=a.project_root)),indent=2,sort_keys=True,default=_json_default))
    return 0
