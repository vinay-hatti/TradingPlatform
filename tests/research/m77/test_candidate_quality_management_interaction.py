import numpy as np
import pandas as pd

from trading_ai.research.m77.candidate_quality_management_interaction import (
    FIXED_STATES,
    _metrics,
    _state_mask,
    interaction_evidence,
    readiness,
)


def _panel():
    rows=[]
    rng=np.random.default_rng(7727)
    symbols=[f"S{i:03d}" for i in range(300)]
    for year in range(2008,2018):
        for d in pd.bdate_range(f"{year}-01-05", periods=30):
            for i,s in enumerate(symbols):
                q=(i%100)/99
                base=.15+0.10*q+rng.normal(0,.25)
                rows.append({
                    "symbol":s,"as_of":d,"entry_date":d+pd.Timedelta(days=1),
                    "r_multiple":base,"exit_type":"TIME",
                    "probability_up":q,"bearish_rank_pct":q,
                    "overall_score":50+50*q,"idi_trade_quality":40+60*q,
                    "score_options_suitability":45+55*q,
                    "px_ret_5":q-.5,"dist_sma_20":q-.5,"atr_pct_14":q,
                })
    p=pd.DataFrame(rows)
    p["calendar_year"]=p["as_of"].dt.year
    for c in ("probability_up","overall_score","idi_trade_quality","score_options_suitability","atr_pct_14"):
        p[f"rank_{c}"]=p.groupby("as_of")[c].rank(pct=True,method="average")
    return p


def test_fixed_state_catalog_is_frozen():
    assert "PROBABILITY_UP_TOP20" in FIXED_STATES
    assert "DRVE_RISK_HIGHER_DECILE" in FIXED_STATES
    assert "BELOW_SMA20" in FIXED_STATES
    assert len(FIXED_STATES)==16


def test_probability_top20_state_is_contemporaneous_rank():
    p=_panel().head(300)
    m=_state_mask(p,"PROBABILITY_UP_TOP20")
    assert 0.15 <= m.mean() <= 0.25


def test_interaction_evidence_detects_quality_gradient():
    p=_panel()
    e,y,n=interaction_evidence(p)
    row=e[e.state=="PROBABILITY_UP_TOP20"].iloc[0]
    assert row.interaction_mean_r_uplift>0
    assert row.state_mean_r>row.complement_mean_r
    assert not y.empty and not n.empty


def test_metrics_are_equal_symbol_and_concentration_aware():
    g=pd.DataFrame({
        "symbol":["A","A","B","C"],
        "r_multiple":[1.0,1.0,-.5,.5],
        "exit_type":["TARGET","TARGET","STOP","TIME"],
    })
    m=_metrics(g)
    assert m["n"]==4
    assert m["symbols"]==3
    assert np.isfinite(m["equal_symbol_mean_r"])
    assert 0 <= m["top10_abs_contribution_fraction"] <= 1


def test_readiness_requires_all_frozen_interaction_gates():
    e=pd.DataFrame([{
        "state":"X","state_fraction":.25,
        "state_n":3000,"state_symbols":300,"state_mean_r":.25,"state_median_r":.2,
        "state_win_rate":.6,"state_profit_factor":1.6,"state_equal_symbol_mean_r":.2,
        "state_positive_symbol_fraction":.75,"state_gap_stop_fraction":.03,
        "state_tail_1pct_r":-1.5,"state_top10_abs_contribution_fraction":.15,
        "complement_n":9000,"complement_symbols":500,"complement_mean_r":.12,
        "complement_profit_factor":1.3,"complement_win_rate":.52,
        "full_mean_r":.15,"interaction_mean_r_uplift":.13,
        "interaction_profit_factor_uplift":.3,"interaction_win_rate_uplift":.08,
        "nonoverlap_state_mean_r":.18,"nonoverlap_state_profit_factor":1.4,
    }])
    years=pd.DataFrame([
        {"state":"X","year":y,"interaction_mean_r_uplift":.1,"interaction_profit_factor_uplift":.2}
        for y in range(2008,2018)
    ])
    r=readiness(e,years)
    assert bool(r.iloc[0].development_ready_interaction)
