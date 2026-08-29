import numpy as np
import pandas as pd

from trading_ai.research.m77.cross_sectional_ranking_opportunity_cost import (
    _metrics,
    _select_topk,
    _simulate_capacity,
    ranking_evidence,
    readiness,
)


def _panel():
    rows=[]
    syms=[f"S{i:02d}" for i in range(20)]
    for y in range(2008,2018):
        for d in pd.bdate_range(f"{y}-01-04", periods=30):
            for i,s in enumerate(syms):
                q=(i+1)/20
                rows.append({
                    "symbol":s,"as_of":d,"entry_date":d+pd.Timedelta(days=1),
                    "r_multiple":-0.1+0.8*q,
                    "exit_day":10+(i%5),
                    "probability_up":q,
                    "bearish_rank_pct":q,
                    "overall_score":q,
                    "idi_trade_quality":q,
                    "score_options_suitability":q,
                    "calendar_year":y,
                    "rank_probability_up":q,
                    "rank_drv_low_risk":q,
                    "rank_overall_score":q,
                    "rank_idi_trade_quality":q,
                    "rank_options_suitability":q,
                    "rank_ensemble_simple":q,
                })
    return pd.DataFrame(rows)


def test_topk_is_per_date_and_deterministic():
    p=_panel()
    s=_select_topk(p,"PROBABILITY_UP",3)
    assert len(s)==p["as_of"].nunique()*3
    assert set(s["symbol"].unique())=={"S17","S18","S19"}


def test_metrics_capture_equal_symbol_and_pf():
    g=pd.DataFrame({
        "symbol":["A","B","C","D"],
        "r_multiple":[1.0,0.5,-0.5,-1.0],
    })
    m=_metrics(g)
    assert m["n"]==4
    assert m["symbols"]==4
    assert np.isfinite(m["profit_factor"])
    assert 0 <= m["top10_abs_contribution_fraction"] <= 1


def test_capacity_skips_when_slots_full():
    d=pd.Timestamp("2015-01-05")
    g=pd.DataFrame([
        {"symbol":f"S{i}","as_of":d,"entry_date":d+pd.Timedelta(days=1),
         "selection_rank":i+1,"exit_day":20,"r_multiple":.2}
        for i in range(10)
    ])
    accepted,diag=_simulate_capacity(g,5)
    assert len(accepted)==5
    assert diag["skipped_capacity"]==5
    assert diag["peak_concurrent"]==5


def test_ranking_evidence_detects_probability_gradient():
    p=_panel()
    e,y,c=ranking_evidence(p)
    row=e[(e.ranker=="PROBABILITY_UP")&(e.top_k==3)].iloc[0]
    assert row.mean_r_uplift>0
    assert row.profit_factor>row.baseline_profit_factor
    assert not y.empty and not c.empty


def test_readiness_requires_capacity_and_year_stability():
    e=pd.DataFrame([{
        "ranker":"PROBABILITY_UP","top_k":3,"n":1500,"symbols":200,
        "mean_r":.35,"median_r":.3,"win_rate":.65,"profit_factor":1.8,
        "equal_symbol_mean_r":.30,"positive_symbol_fraction":.75,
        "top10_abs_contribution_fraction":.15,
        "baseline_mean_r":.20,"baseline_profit_factor":1.4,
        "mean_r_uplift":.15,"pf_uplift":.4,
        "candidate_capture_fraction":.2,"skipped_candidate_fraction":.8,
        "r_per_candidate_date":1.0,
    }])
    years=pd.DataFrame([
        {"ranker":"PROBABILITY_UP","top_k":3,"year":y,
         "selected_n":100,"mean_r_uplift":.1,"pf_uplift":.2}
        for y in range(2008,2018)
    ])
    cap=pd.DataFrame([{
        "ranker":"PROBABILITY_UP","top_k":3,"max_concurrent":10,
        "accepted":900,"skipped_capacity":100,"peak_concurrent":10,
        "capacity_n":900,"capacity_symbols":180,"capacity_mean_r":.28,
        "capacity_median_r":.2,"capacity_win_rate":.6,
        "capacity_profit_factor":1.6,"capacity_equal_symbol_mean_r":.25,
        "capacity_positive_symbol_fraction":.7,
        "capacity_top10_abs_contribution_fraction":.18,
        "capacity_capture_fraction":.9,"opportunity_cost_skipped_r":10.0,
    }])
    r=readiness(e,years,cap)
    assert bool(r.iloc[0].development_ready_ranking)
