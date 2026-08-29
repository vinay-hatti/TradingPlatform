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

VERSION="M77.38.1-CAPITAL-PRIORITY-DEPENDENCY-INCREMENTAL-VALUE-SEMANTIC-FORENSICS-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
HORIZON=60
STOP_ATR=3.0
TARGET_ATR=5.0
TOP_FRACTION=0.20
TOP_K=3

class CapitalPriorityForensicsError(RuntimeError):
    pass

@dataclass(frozen=True)
class CapitalPriorityForensicsConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    output_dir:str="research_data/m77_38_1/capital_priority_dependency_incremental_value_semantic_forensics"


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
    pos=r[r>0]; neg=r[r<0]
    gp=float(pos.sum()); gl=float(-neg.sum())
    return {
        "n":int(len(r)),
        "symbols":int(g.loc[r.index,"symbol"].nunique()),
        "dates":int(g.loc[r.index,"as_of"].nunique()),
        "mean_r":float(r.mean()),
        "median_r":float(r.median()),
        "win_rate":float((r>0).mean()),
        "profit_factor":float(gp/gl) if gl>0 else np.inf,
        "p05_r":float(r.quantile(.05)),
        "loss_1r_rate":float((r<=-1).mean()),
    }

def load_panel(cfg:CapitalPriorityForensicsConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    ep=_resolve(root,cfg.executable_panel_path)
    if not ep.exists():raise CapitalPriorityForensicsError(f"M77.26.1 executable authority missing: {ep}")
    p=pd.read_csv(ep)
    p["as_of"]=pd.to_datetime(p["as_of"],errors="coerce")
    p["entry_date"]=pd.to_datetime(p["entry_date"],errors="coerce")
    p=p[
        (pd.to_numeric(p["horizon"],errors="coerce")==HORIZON)
        &(pd.to_numeric(p["stop_atr"],errors="coerce")==STOP_ATR)
        &(pd.to_numeric(p["target_atr"],errors="coerce")==TARGET_ATR)
    ].copy()
    if p.empty:raise CapitalPriorityForensicsError("Certified M77.26.1 geometry missing")
    if (p["as_of"]>DEVELOPMENT_END).any():
        raise CapitalPriorityForensicsError("M77.38.1 refuses post-2017 evidence")
    required=("symbol","as_of","probability_up","r_multiple")
    missing=[c for c in required if c not in p.columns]
    if missing:raise CapitalPriorityForensicsError(f"Required executable fields missing: {missing}")
    p["symbol"]=p["symbol"].astype(str).str.upper()
    for c in ("probability_up","r_multiple"):
        p[c]=pd.to_numeric(p[c],errors="coerce").replace([np.inf,-np.inf],np.nan)
    if p[["probability_up","r_multiple"]].isna().any().any():
        raise CapitalPriorityForensicsError("Probability/outcome authority contains missing values")
    if p.duplicated(["symbol","as_of"],keep=False).any():
        raise CapitalPriorityForensicsError("Certified geometry is not unique on (symbol, as_of)")
    return p,{
        "rows":int(len(p)),
        "symbols":int(p["symbol"].nunique()),
        "dates":int(p["as_of"].nunique()),
        "first_as_of":p["as_of"].min().date().isoformat(),
        "last_as_of":p["as_of"].max().date().isoformat(),
        "executable_input_sha256":_sha(ep),
        "consumed_2018_2026_rows_read":0,
    }

def annotate(p:pd.DataFrame)->pd.DataFrame:
    x=p.copy()
    x["cohort_n"]=x.groupby("as_of")["symbol"].transform("count")
    x["probability_rank"]=x.groupby("as_of")["probability_up"].rank(ascending=False,method="first")
    x["probability_pct_rank"]=x.groupby("as_of")["probability_up"].rank(pct=True,method="average")
    x["prob_top20"]=x["probability_pct_rank"]>=1.0-TOP_FRACTION
    x["capital_top3"]=x["probability_rank"]<=TOP_K
    return x

def date_subset_forensics(x:pd.DataFrame)->pd.DataFrame:
    rows=[]
    for d,g in x.groupby("as_of"):
        top3=g[g["capital_top3"]]
        top20=g[g["prob_top20"]]
        top3_syms=set(top3["symbol"]); top20_syms=set(top20["symbol"])
        subset=top3_syms.issubset(top20_syms)
        rows.append({
            "as_of":d,
            "cohort_n":int(len(g)),
            "top20_n":int(len(top20)),
            "top3_n":int(len(top3)),
            "top3_subset_of_top20":bool(subset),
            "top3_outside_top20_n":int(len(top3_syms-top20_syms)),
            "top3_mean_r":float(top3["r_multiple"].mean()) if len(top3) else np.nan,
            "top20_mean_r":float(top20["r_multiple"].mean()) if len(top20) else np.nan,
            "top3_minus_top20_mean_r":float(top3["r_multiple"].mean()-top20["r_multiple"].mean()) if len(top3) and len(top20) else np.nan,
        })
    return pd.DataFrame(rows)

def cohort_size_conditioned_effect(x:pd.DataFrame)->tuple[pd.DataFrame,dict[str,Any]]:
    d=date_subset_forensics(x)
    # Frozen strata based on exact same-day cohort size groups; no optimized bins.
    d["cohort_size_stratum"]=pd.cut(
        d["cohort_n"],
        bins=[0,5,10,20,50,10**9],
        labels=["01_05","06_10","11_20","21_50","51_PLUS"],
        right=True,
    )
    rows=[]
    for s,g in d.groupby("cohort_size_stratum",observed=True):
        if g.empty:continue
        rows.append({
            "cohort_size_stratum":str(s),
            "dates":int(len(g)),
            "mean_cohort_n":float(g["cohort_n"].mean()),
            "subset_fraction":float(g["top3_subset_of_top20"].mean()),
            "mean_top3_minus_top20_r":float(g["top3_minus_top20_mean_r"].mean()),
            "median_top3_minus_top20_r":float(g["top3_minus_top20_mean_r"].median()),
            "positive_top3_increment_fraction":float((g["top3_minus_top20_mean_r"]>0).mean()),
        })
    strata=pd.DataFrame(rows)
    weighted=float(np.average(
        strata["mean_top3_minus_top20_r"],
        weights=strata["dates"]
    )) if not strata.empty else np.nan
    return strata,{
        "date_equal_weight_top3_minus_top20_r":float(d["top3_minus_top20_mean_r"].mean()),
        "cohort_size_strata_weighted_top3_minus_top20_r":weighted,
        "positive_top3_increment_date_fraction":float((d["top3_minus_top20_mean_r"]>0).mean()),
    }

def run_forensics(cfg:CapitalPriorityForensicsConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    p,meta=load_panel(cfg)
    x=annotate(p)
    dates=date_subset_forensics(x)
    strata,conditioned=cohort_size_conditioned_effect(x)

    divergence=dates[~dates["top3_subset_of_top20"]].copy()
    subset_fraction=float(dates["top3_subset_of_top20"].mean())
    all_subset=bool(dates["top3_subset_of_top20"].all())

    prob=_metrics(x[x["prob_top20"]])
    top3=_metrics(x[x["capital_top3"]])
    raw_delta=float(top3["mean_r"]-prob["mean_r"])

    x.to_csv(outdir/"annotated_probability_priority_authority.csv.gz",index=False,compression="gzip")
    dates.to_csv(outdir/"top3_top20_date_subset_forensics.csv",index=False)
    divergence.to_csv(outdir/"top3_top20_divergence_dates.csv",index=False)
    strata.to_csv(outdir/"cohort_size_conditioned_incremental_value.csv",index=False)

    summary={
        "version":VERSION,
        "status":"COMPLETE",
        "completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31",
        "consumed_2018_2026_rows_read":0,
        "cpre_rank_source":"PROBABILITY_UP",
        "cpre_definitionally_probability_dependent":True,
        "top3_subset_of_top20_fraction":subset_fraction,
        "top3_exactly_within_top20_all_dates":all_subset,
        "top3_not_subset_date_count":int((~dates["top3_subset_of_top20"]).sum()),
        "top3_subset_date_count":int(dates["top3_subset_of_top20"].sum()),
        "dates":int(len(dates)),
        "divergence_cohort_size_min":int(divergence["cohort_n"].min()) if not divergence.empty else None,
        "divergence_cohort_size_max":int(divergence["cohort_n"].max()) if not divergence.empty else None,
        "divergence_cohort_size_median":float(divergence["cohort_n"].median()) if not divergence.empty else None,
        "probability_top20_metrics":prob,
        "capital_top3_metrics":top3,
        "top3_mean_r_increment_vs_top20_raw":raw_delta,
        "cohort_size_conditioned":conditioned,
        "upstream":meta,
        "new_probability_up_thresholds_tested":0,
        "new_top_k_values_tested":0,
        "management_geometry_retuned":False,
        "m77_23_drv_modified":False,
        "m77_24_1_psve_modified":False,
        "m77_26_2_mge_modified":False,
        "m77_27_1_cqmi_modified":False,
        "m77_30_cpre_modified":False,
        "m77_30_cpre_read":False,
        "automatic_retraining":False,
        "polygon_api_called":False,
        "production_authority_effect":False,
        "next_step":"REVIEW CPRE SEMANTIC DEPENDENCY AND COHORT-SIZE-CONDITIONED INCREMENTAL VALUE; NO THRESHOLD/TOP-K RETUNING",
    }

    _atomic_json(outdir/"capital_priority_dependency_incremental_value_summary.json",summary)
    _atomic_json(outdir/"run_manifest.json",{
        "version":VERSION,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "top_fraction":TOP_FRACTION,
        "top_k":TOP_K,
        "cohort_size_strata":["01_05","06_10","11_20","21_50","51_PLUS"],
        "forbidden_outcome_window":"2018-01-01 THROUGH 2026-12-31",
        "production_authority_effect":False,
        "upstream":meta,
    })

    report=[
        "# M77.38.1 Capital-Priority Dependency & Incremental-Value Semantic Forensics","",
        f"- CPRE rank source: PROBABILITY_UP",
        f"- Definitionally probability-dependent: true",
        f"- Top3 subset of Top20 fraction: {subset_fraction:.6f}",
        f"- Top3 within Top20 on all dates: {all_subset}",
        f"- Raw Top3 minus Top20 mean R: {raw_delta:.6f}",
        "",
        "## Cohort-size-conditioned incremental value","",
        strata.to_string(index=False),"",
        "## Divergence dates","",
        divergence.to_string(index=False),
    ]
    (outdir/"CAPITAL_PRIORITY_DEPENDENCY_INCREMENTAL_VALUE_REPORT.md").write_text("\n".join(report))
    return summary

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.38.1 capital priority dependency and incremental-value semantic forensics")
    p.add_argument("--project-root",required=True)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    print(json.dumps(run_forensics(CapitalPriorityForensicsConfig(project_root=a.project_root)),indent=2,sort_keys=True,default=_json_default))
    return 0
