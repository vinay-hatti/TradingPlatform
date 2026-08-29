import numpy as np
import pandas as pd

from trading_ai.research.m77.ensemble_attribution_capacity_regime_neutralization import (
    ensemble_attribution,
    _weighted_gap,
    capacity_neutralization,
)

def _panel():
    rows=[]
    syms=[f"S{i}" for i in range(6)]
    for d in pd.bdate_range("2015-01-05",periods=30):
        for i,s in enumerate(syms):
            q=(i+1)/6
            rows.append({
                "symbol":s,"as_of":d,"entry_date":d+pd.Timedelta(days=1),
                "r_multiple":-.2+.5*q,
                "exit_day":5+i,
                "probability_up":q,
                "bearish_rank_pct":q,
                "overall_score":1-q,
                "idi_trade_quality":q,
                "score_options_suitability":q,
                "calendar_year":d.year,
                "calendar_month":d.to_period("M").strftime("%Y-%m"),
                "rank_probability_up":q,
                "rank_drv_low_risk":q,
                "rank_overall_score":1-q,
                "rank_idi_trade_quality":q,
                "rank_options_suitability":q,
            })
    p=pd.DataFrame(rows)
    p["rank_ensemble_simple"]=p[[
        "rank_probability_up","rank_drv_low_risk","rank_overall_score",
        "rank_idi_trade_quality","rank_options_suitability"
    ]].mean(axis=1)
    return p

def test_ensemble_attribution_produces_leave_one_out_rows():
    p=_panel()
    cmp,comp,loo=ensemble_attribution(p)
    assert len(cmp)==p["as_of"].nunique()
    assert len(loo)==5
    assert set(loo["omitted_component"])=={
        "rank_probability_up","rank_drv_low_risk","rank_overall_score",
        "rank_idi_trade_quality","rank_options_suitability"
    }

def test_weighted_gap_recovers_known_difference():
    df=pd.DataFrame({
        "capacity_cohort":["ACCEPTED","SKIPPED"]*3,
        "bucket":["A","A","B","B","C","C"],
        "r_multiple":[.3,.1,.4,.2,.5,.3],
    })
    r=_weighted_gap(df,["bucket"])
    assert r["strata"]==3
    assert abs(r["equal_stratum_mean_gap_r"]-.2)<1e-12
    assert abs(r["matched_size_weighted_gap_r"]-.2)<1e-12

def test_capacity_neutralization_returns_regime_summaries():
    p=_panel()
    regime=pd.DataFrame({
        "as_of":sorted(p["as_of"].unique()),
        "volatility_state":["LOW","HIGH"]*15,
        "trend_state":["STRONG","WEAK"]*15,
    })
    n,c=capacity_neutralization(p,regime)
    assert not n.empty
    assert "YEAR" in set(n["neutralization"])
    assert any(str(x).startswith("REGIME::") for x in n["neutralization"])
    assert set(c["capacity_cohort"])=={"ACCEPTED","SKIPPED"}
