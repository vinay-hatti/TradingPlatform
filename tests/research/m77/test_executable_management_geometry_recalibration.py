import numpy as np
import pandas as pd

from trading_ai.research.m77.executable_management_geometry_recalibration import (
    _metrics,
    _simulate_executable,
    readiness,
)


def _future(rows):
    return pd.DataFrame(rows,columns=["open","high","low","close"])


def test_gap_through_stop_fills_at_open_and_can_lose_more_than_one_r():
    fut=_future([
        [96.0,99.0,95.0,97.0],
        [98.0,100.0,97.0,99.0],
    ])
    # entry 100, atr 2, stop 1 ATR => stop 98, open gaps to 96.
    r=_simulate_executable(fut,100.0,2.0,3.0,1.0,99.0)
    assert r["exit_type"]=="STOP_GAP"
    assert r["exit_price"]==96.0
    assert r["r_multiple"]==-2.0
    assert r["stop_slippage_r"]==-1.0


def test_target_gap_is_capped_at_target_price():
    fut=_future([[108.0,110.0,107.0,109.0]])
    # 2ATR target from 100 with ATR2 => 104.
    r=_simulate_executable(fut,100.0,2.0,2.0,2.0,109.0)
    assert r["exit_type"]=="TARGET_GAP"
    assert r["exit_price"]==104.0
    assert r["r_multiple"]==1.0


def test_same_bar_target_and_stop_is_conservative_stop():
    fut=_future([[100.0,105.0,97.0,102.0]])
    r=_simulate_executable(fut,100.0,2.0,2.0,1.0,102.0)
    assert r["exit_type"]=="AMBIGUOUS_STOP_CONSERVATIVE"
    assert r["r_multiple"]==-1.0
    assert r["ambiguous_bar"] is True


def test_unresolved_trade_exits_at_horizon_close():
    fut=_future([
        [100.0,101.0,99.0,100.5],
        [100.5,102.0,100.0,101.5],
    ])
    r=_simulate_executable(fut,100.0,2.0,3.0,2.0,101.5)
    assert r["exit_type"]=="TIME"
    assert abs(r["r_multiple"]-0.375)<1e-12


def test_metrics_include_all_exit_types_and_gap_slippage():
    g=pd.DataFrame([
        {"symbol":"A","r_multiple":1.0,"exit_type":"TARGET","ambiguous_bar":False,"stop_slippage_r":0.0},
        {"symbol":"B","r_multiple":-1.0,"exit_type":"STOP","ambiguous_bar":False,"stop_slippage_r":0.0},
        {"symbol":"C","r_multiple":-1.5,"exit_type":"STOP_GAP","ambiguous_bar":False,"stop_slippage_r":-0.5},
        {"symbol":"D","r_multiple":0.25,"exit_type":"TIME","ambiguous_bar":False,"stop_slippage_r":0.0},
    ])
    m=_metrics(g)
    assert m["n"]==4
    assert m["gap_stop_fraction"]==0.25
    assert m["time_exit_fraction"]==0.25
    assert m["mean_stop_slippage_r"]==-0.5


def test_readiness_uses_full_cohort_executable_gates():
    e=pd.DataFrame([{
        "horizon":30,"target_atr":3.0,"stop_atr":2.5,"n":10000,"symbols":500,
        "mean_r":.12,"median_r":.05,"win_rate":.56,"loss_rate":.44,"profit_factor":1.30,
        "target_exit_fraction":.4,"stop_exit_fraction":.4,"time_exit_fraction":.2,
        "ambiguous_fraction":.01,"gap_stop_fraction":.02,"mean_stop_slippage_r":-.1,
        "mean_time_exit_r":.03,"tail_loss_5pct_r":-1.0,"tail_loss_1pct_r":-1.8,
        "equal_symbol_mean_r":.10,"positive_symbol_fraction":.65,
        "largest_symbol_abs_contribution_fraction":.02,"top10_symbol_abs_contribution_fraction":.12,
    }])
    years=pd.DataFrame([
        {"horizon":30,"target_atr":3.0,"stop_atr":2.5,"year":y,"mean_r":.10,"profit_factor":1.2}
        for y in range(2008,2018)
    ])
    non=pd.DataFrame([{
        "horizon":30,"target_atr":3.0,"stop_atr":2.5,"n":7000,"mean_r":.09,
        "profit_factor":1.2,"equal_symbol_mean_r":.08,
    }])
    r=readiness(e,years,non)
    assert bool(r.iloc[0]["development_ready_executable"])
