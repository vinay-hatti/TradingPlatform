import pandas as pd
import numpy as np

from trading_ai.research.m77.capacity_constrained_portfolio_utility import (
    _candidate_order, certification, portfolio_metrics, simulate_policy, run_all
)

def _panel():
    rows=[]
    for di,d in enumerate(pd.bdate_range("2015-01-05",periods=40)):
        for i in range(8):
            rows.append({
                "symbol":f"S{i}",
                "as_of":d,
                "entry_date":d+pd.offsets.BDay(1),
                "exit_day":3+(i%2),
                "r_multiple":-0.3+0.12*i,
                "probability_up":0.50+0.04*i,
                "probability_rank":8-i,
                "probability_pct_rank":(i+1)/8,
                "prob_top20":(i+1)/8>=0.80,
                "cpre_top3":8-i<=3,
            })
    return pd.DataFrame(rows)

def test_candidate_order_cpre_is_top3_only():
    p=_panel()
    g=p[p["as_of"]==p["as_of"].min()]
    x=_candidate_order(g,"CPRE_TOP3")
    assert len(x)==3
    assert (x["probability_rank"]<=3).all()

def test_capacity_is_never_exceeded():
    p=_panel()
    trades,daily=simulate_policy(p,"CPRE_TOP3",3)
    assert (daily["occupied_after"]<=3).all()
    assert not trades.empty

def test_ranked_fill_uses_signal_order():
    p=_panel()
    g=p[p["as_of"]==p["as_of"].min()]
    x=_candidate_order(g,"PROBABILITY_RANKED_FILL")
    assert list(x["probability_rank"])==sorted(x["probability_rank"])

def test_equal_priority_ignores_probability_order():
    p=_panel()
    g=p[p["as_of"]==p["as_of"].min()]
    x=_candidate_order(g,"TOP20_EQUAL_PRIORITY")
    assert list(x["symbol"])==sorted(x["symbol"])

def test_portfolio_metrics_present():
    p=_panel()
    trades,daily=simulate_policy(p,"CPRE_TOP3",3)
    m=portfolio_metrics(trades,daily)
    for k in ("cumulative_r","return_per_slot","mean_utilization","max_cumulative_r_drawdown"):
        assert k in m

def test_run_all_covers_all_frozen_capacities_and_policies():
    p=_panel()
    s,t,d=run_all(p)
    assert set(s["capacity_slots"])=={3,5,10}
    assert set(s["policy"])=={
        "CPRE_TOP3","PROBABILITY_RANKED_FILL","TOP20_EQUAL_PRIORITY","DETERMINISTIC_FIRST_AVAILABLE"
    }

def test_certification_is_explicit():
    p=_panel()
    s,_,_=run_all(p)
    cert,cmp=certification(s)
    assert cert["primary_capacity_slots"]==3
    assert cert["primary_policy"]=="CPRE_TOP3"
    assert cert["certification_verdict"] in {"PASS","FAIL"}
    assert len(cmp)==2
