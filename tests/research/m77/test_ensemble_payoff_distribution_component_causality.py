import numpy as np
import pandas as pd

from trading_ai.research.m77.ensemble_payoff_distribution_component_causality import (
    _metrics_from_diff,
    _tail_contribution,
    component_causality,
    divergence_distribution,
    component_outcome_attribution,
)

def _panel():
    rows=[]
    syms=[f"S{i}" for i in range(8)]
    for d in pd.bdate_range("2015-01-05",periods=40):
        for i,s in enumerate(syms):
            q=(i+1)/8
            rows.append({
                "symbol":s,"as_of":d,"entry_date":d+pd.Timedelta(days=1),
                "r_multiple":-.3+.8*q + (0.25 if (i==5 and d.day%5==0) else 0),
                "exit_day":10+i,
                "probability_up":q,
                "bearish_rank_pct":q,
                "overall_score":1-q if i%2==0 else q,
                "idi_trade_quality":q,
                "score_options_suitability":q,
                "calendar_year":d.year,
                "rank_probability_up":q,
                "rank_drv_low_risk":q,
                "rank_overall_score":1-q if i%2==0 else q,
                "rank_idi_trade_quality":q,
                "rank_options_suitability":q,
            })
    p=pd.DataFrame(rows)
    p["rank_ensemble_simple"]=p[[
        "rank_probability_up","rank_drv_low_risk","rank_overall_score",
        "rank_idi_trade_quality","rank_options_suitability"
    ]].mean(axis=1)
    return p

def test_distribution_metrics_and_tail_contribution():
    s=pd.Series([1.0,.5,.2,-.1,-.2])
    m=_metrics_from_diff(s)
    assert m["n"]==5
    assert m["positive_fraction"]==.6
    t=_tail_contribution(s)
    assert len(t)==4
    assert (t["share_of_total_positive_advantage"]<=1).all()

def test_divergence_distribution_materializes():
    p=_panel()
    cmp,div,tail=divergence_distribution(p)
    assert len(cmp)==p["as_of"].nunique()
    assert set(["same_symbol","ensemble_minus_probability_r"]).issubset(cmp.columns)
    assert len(tail)==4

def test_leave_one_component_out_has_all_frozen_components():
    p=_panel()
    loo,yr=component_causality(p)
    assert len(loo)==5
    assert set(loo["omitted_component"])=={
        "rank_probability_up","rank_drv_low_risk","rank_overall_score",
        "rank_idi_trade_quality","rank_options_suitability"
    }
    assert not yr.empty

def test_component_outcome_attribution_reports_correlations():
    d=pd.DataFrame({
        "component":["A"]*5,
        "ensemble_minus_probability_component_rank":[.1,.2,-.1,.3,-.2],
        "ensemble_minus_probability_r":[.2,.4,-.1,.5,-.3],
        "ensemble_wins":[True,True,False,True,False],
    })
    r=component_outcome_attribution(d)
    assert len(r)==1
    assert r.iloc[0]["n"]==5
    assert np.isfinite(r.iloc[0]["rank_delta_vs_r_pearson"])
