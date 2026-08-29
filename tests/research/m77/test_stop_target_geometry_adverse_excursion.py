import numpy as np
import pandas as pd

from trading_ai.research.m77.stop_target_geometry_adverse_excursion import (
    _barrier_result,
    _resolved_metrics,
    excursion_evidence,
    readiness,
)


def test_barrier_target_before_stop_and_same_bar_ambiguity():
    highs=np.array([101.0,104.5,105.0])
    lows=np.array([99.5,99.0,98.5])
    result,td,sd=_barrier_result(highs,lows,100.0,2.0,2.0,1.0)
    assert result==1.0
    assert td==2.0
    # Same future daily bar target+stop must remain ambiguous.
    highs=np.array([104.5])
    lows=np.array([97.5])
    result,td,sd=_barrier_result(highs,lows,100.0,2.0,2.0,1.0)
    assert np.isnan(result)


def test_resolved_expectancy_uses_target_stop_r_multiple():
    g=pd.DataFrame({
        "symbol":["A","B","C","D"],
        "barrier_t2p0_s1p0":[1.0,1.0,-1.0,-1.0],
        "target_day_t2p0_s1p0":[2,3,np.nan,np.nan],
        "stop_day_t2p0_s1p0":[np.nan,np.nan,1,2],
    })
    m=_resolved_metrics(g,2.0,1.0)
    assert m["resolved_n"]==4
    assert m["target_first_rate"]==0.5
    assert abs(m["expectancy_r"]-0.5)<1e-12


def test_excursion_evidence_reports_winner_stop_survival():
    rows=[]
    for h in (10,15,20,30,45,60):
        rows.extend([
            {"horizon":h,"terminal_return":.10,"mfe_atr":3.0,"mae_atr":-.5},
            {"horizon":h,"terminal_return":.05,"mfe_atr":2.0,"mae_atr":-1.2},
            {"horizon":h,"terminal_return":-.05,"mfe_atr":.6,"mae_atr":-2.0},
        ])
    p=pd.DataFrame(rows)
    q,l,s=excursion_evidence(p)
    row=s[(s.horizon==20)&(s.stop_atr==1.0)].iloc[0]
    assert row.eventual_winners==2
    assert row.winner_fraction_surviving_stop==0.5
    assert not q.empty and not l.empty


def test_readiness_requires_all_frozen_gates():
    geom=pd.DataFrame([{
        "horizon":30,"target_atr":3.0,"stop_atr":2.0,
        "resolved_n":2500,"resolved_symbols":400,"resolved_fraction":.7,
        "expectancy_r":.20,"equal_symbol_expectancy_r":.15,
        "positive_symbol_fraction":.65,
        "largest_symbol_abs_contribution_fraction":.03,
        "top10_symbol_abs_contribution_fraction":.22,
    }])
    years=pd.DataFrame([
        {"horizon":30,"target_atr":3.0,"stop_atr":2.0,"year":y,"expectancy_r":.1}
        for y in range(2008,2018)
    ])
    non=pd.DataFrame([{
        "horizon":30,"target_atr":3.0,"stop_atr":2.0,
        "resolved_n":1500,"expectancy_r":.12,"equal_symbol_expectancy_r":.10,
    }])
    r=readiness(geom,years,non)
    assert bool(r.iloc[0].development_ready)
