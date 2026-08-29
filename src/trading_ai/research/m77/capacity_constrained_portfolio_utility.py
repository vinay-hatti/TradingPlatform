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

VERSION="M77.39.0-CAPACITY-CONSTRAINED-PORTFOLIO-UTILITY-CAPITAL-ALLOCATION-CERTIFICATION-1.0"
DEVELOPMENT_END=pd.Timestamp("2017-12-31")
HORIZON=60
STOP_ATR=3.0
TARGET_ATR=5.0

TOP20_FRACTION=0.20
CPRE_TOP_K=3
CAPACITY_SLOTS=(3,5,10)
PRIMARY_CAPACITY=3

POLICIES=(
    "CPRE_TOP3",
    "PROBABILITY_RANKED_FILL",
    "TOP20_EQUAL_PRIORITY",
    "DETERMINISTIC_FIRST_AVAILABLE",
)

class PortfolioUtilityError(RuntimeError):
    pass

@dataclass(frozen=True)
class PortfolioUtilityConfig:
    project_root:str
    executable_panel_path:str="research_data/m77_26_1/executable_management_geometry_recalibration/executable_geometry_observation_panel.csv.gz"
    output_dir:str="research_data/m77_39/capacity_constrained_portfolio_utility_capital_allocation_certification"


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

def load_panel(cfg:PortfolioUtilityConfig)->tuple[pd.DataFrame,dict[str,Any]]:
    root=Path(cfg.project_root).expanduser().resolve()
    ep=_resolve(root,cfg.executable_panel_path)
    if not ep.exists():
        raise PortfolioUtilityError(f"M77.26.1 executable authority missing: {ep}")
    p=pd.read_csv(ep)
    p["as_of"]=pd.to_datetime(p["as_of"],errors="coerce")
    p["entry_date"]=pd.to_datetime(p["entry_date"],errors="coerce")
    p=p[
        (pd.to_numeric(p["horizon"],errors="coerce")==HORIZON)
        &(pd.to_numeric(p["stop_atr"],errors="coerce")==STOP_ATR)
        &(pd.to_numeric(p["target_atr"],errors="coerce")==TARGET_ATR)
    ].copy()
    if p.empty:
        raise PortfolioUtilityError("Certified 5ATR/3ATR/60d executable geometry missing")
    if (p["as_of"]>DEVELOPMENT_END).any():
        raise PortfolioUtilityError("M77.39 refuses post-2017 evidence")

    required=("symbol","as_of","entry_date","exit_day","r_multiple","probability_up")
    missing=[c for c in required if c not in p.columns]
    if missing:
        raise PortfolioUtilityError(f"Required executable fields missing: {missing}")

    p["symbol"]=p["symbol"].astype(str).str.upper()
    for c in ("exit_day","r_multiple","probability_up"):
        p[c]=pd.to_numeric(p[c],errors="coerce").replace([np.inf,-np.inf],np.nan)
    if p[list(required[3:])].isna().any().any():
        raise PortfolioUtilityError("Executable portfolio-utility authority contains missing values")
    if p.duplicated(["symbol","as_of"],keep=False).any():
        raise PortfolioUtilityError("Certified geometry is not unique on (symbol, as_of)")

    p["probability_rank"]=p.groupby("as_of")["probability_up"].rank(ascending=False,method="first")
    p["probability_pct_rank"]=p.groupby("as_of")["probability_up"].rank(pct=True,method="average")
    p["prob_top20"]=p["probability_pct_rank"]>=1.0-TOP20_FRACTION
    p["cpre_top3"]=p["probability_rank"]<=CPRE_TOP_K

    return p,{
        "rows":int(len(p)),
        "symbols":int(p["symbol"].nunique()),
        "dates":int(p["as_of"].nunique()),
        "first_as_of":p["as_of"].min().date().isoformat(),
        "last_as_of":p["as_of"].max().date().isoformat(),
        "executable_input_sha256":_sha(ep),
        "consumed_2018_2026_rows_read":0,
    }

def _candidate_order(g:pd.DataFrame,policy:str)->pd.DataFrame:
    if policy=="CPRE_TOP3":
        return g[g["cpre_top3"]].sort_values(["probability_rank","symbol"])
    if policy=="PROBABILITY_RANKED_FILL":
        return g.sort_values(["probability_rank","symbol"])
    if policy=="TOP20_EQUAL_PRIORITY":
        # Equal-priority means no predictive rank among Top20. Symbol is only deterministic tie order.
        return g[g["prob_top20"]].sort_values(["symbol"])
    if policy=="DETERMINISTIC_FIRST_AVAILABLE":
        # No signal priority: deterministic symbol order across all qualified candidates.
        return g.sort_values(["symbol"])
    raise KeyError(policy)

def simulate_policy(p:pd.DataFrame,policy:str,capacity_slots:int)->tuple[pd.DataFrame,pd.DataFrame]:
    if capacity_slots<1: raise ValueError("capacity_slots must be positive")
    active=[]  # list of dicts with release_date and trade id
    accepted=[]
    daily=[]

    dates=sorted(pd.Timestamp(d) for d in p["as_of"].dropna().unique())
    for d in dates:
        # Release positions whose modeled exit is before/at this decision date.
        active=[a for a in active if a["release_date"]>d]
        free=max(0,capacity_slots-len(active))
        g=p[p["as_of"]==d]
        ordered=_candidate_order(g,policy)
        considered=int(len(ordered))
        accepted_today=0
        skipped_capacity=0

        for _,row in ordered.iterrows():
            if free<=0:
                skipped_capacity+=1
                continue
            exit_day=max(1,int(row["exit_day"]))
            release_date=pd.Timestamp(row["entry_date"])+pd.offsets.BDay(exit_day)
            accepted.append({
                "policy":policy,
                "capacity_slots":capacity_slots,
                "symbol":row["symbol"],
                "as_of":row["as_of"],
                "entry_date":row["entry_date"],
                "release_date":release_date,
                "probability_rank":float(row["probability_rank"]),
                "probability_up":float(row["probability_up"]),
                "r_multiple":float(row["r_multiple"]),
                "exit_day":exit_day,
            })
            active.append({"release_date":release_date,"symbol":row["symbol"]})
            free-=1
            accepted_today+=1

        daily.append({
            "policy":policy,
            "capacity_slots":capacity_slots,
            "as_of":d,
            "active_before_new":int(capacity_slots-max(0,capacity_slots-len(active)+accepted_today)),
            "considered":considered,
            "accepted_today":accepted_today,
            "skipped_capacity":skipped_capacity,
            "occupied_after":len(active),
            "utilization_after":len(active)/capacity_slots,
        })
    return pd.DataFrame(accepted),pd.DataFrame(daily)

def portfolio_metrics(trades:pd.DataFrame,daily:pd.DataFrame)->dict[str,Any]:
    if trades.empty:
        return {"accepted_n":0}
    r=trades["r_multiple"].astype(float)
    pos=r[r>0];neg=r[r<0]
    gp=float(pos.sum());gl=float(-neg.sum())
    monthly=trades.assign(month=trades["entry_date"].dt.to_period("M")).groupby("month")["r_multiple"].sum()
    yearly=trades.assign(year=trades["entry_date"].dt.year).groupby("year")["r_multiple"].sum()
    cumulative=r.cumsum()
    drawdown=cumulative-cumulative.cummax()
    return {
        "accepted_n":int(len(trades)),
        "symbols":int(trades["symbol"].nunique()),
        "dates_with_acceptance":int(trades["as_of"].nunique()),
        "cumulative_r":float(r.sum()),
        "mean_r_per_trade":float(r.mean()),
        "median_r_per_trade":float(r.median()),
        "win_rate":float((r>0).mean()),
        "profit_factor":float(gp/gl) if gl>0 else np.inf,
        "p05_trade_r":float(r.quantile(.05)),
        "loss_1r_rate":float((r<=-1).mean()),
        "max_cumulative_r_drawdown":float(drawdown.min()),
        "positive_month_fraction":float((monthly>0).mean()) if len(monthly) else np.nan,
        "positive_year_fraction":float((yearly>0).mean()) if len(yearly) else np.nan,
        "mean_monthly_r":float(monthly.mean()) if len(monthly) else np.nan,
        "worst_month_r":float(monthly.min()) if len(monthly) else np.nan,
        "mean_utilization":float(daily["utilization_after"].mean()) if not daily.empty else np.nan,
        "capacity_saturation_fraction":float((daily["utilization_after"]>=1.0).mean()) if not daily.empty else np.nan,
        "return_per_slot":float(r.sum()/int(daily["capacity_slots"].iloc[0])) if not daily.empty else np.nan,
        "return_per_accepted_trade":float(r.mean()),
        "skipped_capacity_total":int(daily["skipped_capacity"].sum()) if not daily.empty else 0,
    }

def run_all(p:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    summary_rows=[]
    all_trades=[]
    all_daily=[]
    for cap in CAPACITY_SLOTS:
        for policy in POLICIES:
            trades,daily=simulate_policy(p,policy,cap)
            m=portfolio_metrics(trades,daily)
            summary_rows.append({"policy":policy,"capacity_slots":cap,**m})
            all_trades.append(trades)
            all_daily.append(daily)
    return pd.DataFrame(summary_rows),pd.concat(all_trades,ignore_index=True),pd.concat(all_daily,ignore_index=True)

def certification(summary:pd.DataFrame)->tuple[dict[str,Any],pd.DataFrame]:
    s=summary[summary["capacity_slots"]==PRIMARY_CAPACITY].set_index("policy")
    required=set(POLICIES)
    if not required.issubset(set(s.index)):
        raise PortfolioUtilityError("Primary-capacity policy results incomplete")
    cpre=s.loc["CPRE_TOP3"]
    comparators=["TOP20_EQUAL_PRIORITY","DETERMINISTIC_FIRST_AVAILABLE"]
    rows=[]
    for comp in comparators:
        b=s.loc[comp]
        rows.append({
            "comparator":comp,
            "delta_cumulative_r":float(cpre["cumulative_r"]-b["cumulative_r"]),
            "delta_return_per_slot":float(cpre["return_per_slot"]-b["return_per_slot"]),
            "delta_profit_factor":(
                float(cpre["profit_factor"]-b["profit_factor"])
                if np.isfinite(cpre["profit_factor"]) and np.isfinite(b["profit_factor"])
                else np.nan
            ),
            "delta_max_drawdown":float(cpre["max_cumulative_r_drawdown"]-b["max_cumulative_r_drawdown"]),
            "delta_positive_month_fraction":float(cpre["positive_month_fraction"]-b["positive_month_fraction"]),
            "delta_worst_month_r":float(cpre["worst_month_r"]-b["worst_month_r"]),
            "delta_mean_utilization":float(cpre["mean_utilization"]-b["mean_utilization"]),
        })
    cmp=pd.DataFrame(rows)
    gates={
        "cpre_cumulative_r_positive":bool(cpre["cumulative_r"]>0),
        "cpre_profit_factor_above_one":bool(cpre["profit_factor"]>1.0),
        "cpre_beats_equal_priority_cumulative_r":bool(cmp.set_index("comparator").loc["TOP20_EQUAL_PRIORITY","delta_cumulative_r"]>0),
        "cpre_beats_first_available_cumulative_r":bool(cmp.set_index("comparator").loc["DETERMINISTIC_FIRST_AVAILABLE","delta_cumulative_r"]>0),
        "cpre_beats_equal_priority_return_per_slot":bool(cmp.set_index("comparator").loc["TOP20_EQUAL_PRIORITY","delta_return_per_slot"]>0),
        "cpre_beats_first_available_return_per_slot":bool(cmp.set_index("comparator").loc["DETERMINISTIC_FIRST_AVAILABLE","delta_return_per_slot"]>0),
        "cpre_positive_month_fraction_at_least_0_55":bool(cpre["positive_month_fraction"]>=0.55),
        "cpre_drawdown_not_worse_than_first_available":bool(cmp.set_index("comparator").loc["DETERMINISTIC_FIRST_AVAILABLE","delta_max_drawdown"]>=0),
    }
    verdict="PASS" if all(gates.values()) else "FAIL"
    return {
        "primary_capacity_slots":PRIMARY_CAPACITY,
        "primary_policy":"CPRE_TOP3",
        "certification_verdict":verdict,
        "gates":gates,
        "cpre_primary_metrics":cpre.to_dict(),
    },cmp

def run_lab(cfg:PortfolioUtilityConfig)->dict[str,Any]:
    root=Path(cfg.project_root).expanduser().resolve()
    outdir=_resolve(root,cfg.output_dir);outdir.mkdir(parents=True,exist_ok=True)
    p,meta=load_panel(cfg)
    summary,trades,daily=run_all(p)
    cert,comparisons=certification(summary)

    summary.to_csv(outdir/"portfolio_policy_capacity_summary.csv",index=False)
    trades.to_csv(outdir/"portfolio_policy_accepted_trades.csv.gz",index=False,compression="gzip")
    daily.to_csv(outdir/"portfolio_policy_daily_capacity_state.csv.gz",index=False,compression="gzip")
    comparisons.to_csv(outdir/"primary_capacity_policy_comparisons.csv",index=False)

    result={
        "version":VERSION,
        "status":"COMPLETE",
        "completed_at":datetime.now(timezone.utc).isoformat(),
        "development_boundary":"2017-12-31",
        "consumed_2018_2026_rows_read":0,
        "certified_management_geometry":{"entry":"NEXT_OPEN","horizon":60,"stop_atr":3.0,"target_atr":5.0},
        "policies_tested":list(POLICIES),
        "capacity_slots_tested":list(CAPACITY_SLOTS),
        "probability_top_fraction":TOP20_FRACTION,
        "cpre_top_k":CPRE_TOP_K,
        "primary_certification":cert,
        "upstream":meta,
        "new_probability_up_thresholds_tested":0,
        "new_top_k_values_tested":0,
        "capacity_budgets_retuned":False,
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
        "next_step":"REVIEW PORTFOLIO-UTILITY CERTIFICATION; NO AUTOMATIC CPRE OR PRODUCTION CHANGE",
    }
    _atomic_json(outdir/"capacity_constrained_portfolio_utility_summary.json",result)
    _atomic_json(outdir/"run_manifest.json",{
        "version":VERSION,
        "created_at":datetime.now(timezone.utc).isoformat(),
        "policies":list(POLICIES),
        "capacity_slots":list(CAPACITY_SLOTS),
        "primary_capacity":PRIMARY_CAPACITY,
        "top_fraction":TOP20_FRACTION,
        "top_k":CPRE_TOP_K,
        "forbidden_outcome_window":"2018-01-01 THROUGH 2026-12-31",
        "production_authority_effect":False,
        "upstream":meta,
    })

    report=[
        "# M77.39 Capacity-Constrained Portfolio Utility & Capital Allocation Certification","",
        "## Primary certification","",
        json.dumps(cert,indent=2,sort_keys=True,default=_json_default),"",
        "## Policy / capacity summary","",
        summary.to_string(index=False),"",
        "## Primary-capacity comparisons","",
        comparisons.to_string(index=False),
    ]
    (outdir/"CAPACITY_CONSTRAINED_PORTFOLIO_UTILITY_REPORT.md").write_text("\n".join(report))
    return result

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="M77.39 capacity-constrained portfolio utility and capital allocation certification")
    p.add_argument("--project-root",required=True)
    return p

def main(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    print(json.dumps(run_lab(PortfolioUtilityConfig(project_root=a.project_root)),indent=2,sort_keys=True,default=_json_default))
    return 0
