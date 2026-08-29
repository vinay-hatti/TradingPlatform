import numpy as np
import pandas as pd

from trading_ai.research.m77.ranking_identity_independence_capacity_forensics import (
    _rank_corr_rows,
    _top_overlap,
    _transformation_forensics,
    ensemble_independence,
    capacity_forensics,
)

def _panel():
    rows=[]
    syms=[f"S{i}" for i in range(6)]
    for d in pd.bdate_range("2015-01-05",periods=20):
        for i,s in enumerate(syms):
            p=(i+1)/6
            rows.append({
                "symbol":s,"as_of":d,"entry_date":d+pd.Timedelta(days=1),
                "probability_up":p,
                "bearish_rank_pct":p,
                "overall_score":1-p,
                "idi_trade_quality":p,
                "score_options_suitability":p,
                "r_multiple":-.2+.5*p,
                "exit_day":5+i,
                "calendar_year":d.year,
            })
    x=pd.DataFrame(rows)
    for c,new in [
        ("probability_up","rank_probability_up"),
        ("bearish_rank_pct","rank_drv_low_risk"),
        ("overall_score","rank_overall_score"),
        ("idi_trade_quality","rank_idi_trade_quality"),
        ("score_options_suitability","rank_options_suitability"),
    ]:
        x[new]=x.groupby("as_of")[c].rank(pct=True,method="average")
    x["rank_ensemble_simple"]=x[[
        "rank_probability_up","rank_drv_low_risk","rank_overall_score",
        "rank_idi_trade_quality","rank_options_suitability"
    ]].mean(axis=1)
    return x

def test_identity_detects_identical_rankings():
    p=_panel()
    c=_rank_corr_rows(p)
    assert np.allclose(c["spearman_probability_vs_drv"],1.0)
    assert c["exact_full_order_equal"].all()

def test_topk_overlap_identical_is_one():
    p=_panel()
    o=_top_overlap(p)
    assert np.allclose(o["mean_set_overlap_fraction"],1.0)
    assert np.allclose(o["exact_order_match_fraction"],1.0)

def test_affine_forensics_detects_exact_equal():
    p=_panel()
    r=_transformation_forensics(p)
    assert r["exact_equal_fraction"]==1.0
    assert abs(r["affine_slope"]-1.0)<1e-12
    assert abs(r["affine_intercept"])<1e-12

def test_ensemble_can_diverge_from_probability():
    p=_panel()
    # overall_score is inverted, so ensemble may differ depending on balance
    e,d=ensemble_independence(p)
    assert len(e)==p["as_of"].nunique()
    assert "same_symbol" in e.columns

def test_capacity_forensics_partitions_selected():
    p=_panel()
    cap,events=capacity_forensics(p)
    base=cap[cap["cohort"].isin(["SELECTED_ALL","CAPACITY_ACCEPTED","CAPACITY_SKIPPED"])]
    assert len(base)==3
    assert len(events)>0
