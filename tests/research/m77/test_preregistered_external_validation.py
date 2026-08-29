from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from trading_ai.research.m77.preregistered_external_validation import (
    PRIMARY_GATES, ValidationConfig, _evaluate_primary_gates, _select_cross_section, preregistration_payload,
)


def test_preregistration_is_frozen_and_final_holdout_closed():
    p=preregistration_payload()
    assert p["registered_before_validation_open"] is True
    assert p["primary_hypothesis"]["horizon_sessions"] == 20
    assert p["primary_hypothesis"]["tail_fraction"] == 0.01
    assert p["governance"]["final_holdout_open_authorized"] is False
    assert p["governance"]["validation_model_refit"] is False
    assert len(p["preregistration_sha256"]) == 64


def test_config_refuses_protocol_mutation():
    ValidationConfig(project_root="/tmp").validate()
    with pytest.raises(Exception):
        ValidationConfig(project_root="/tmp",max_features=79).validate()
    with pytest.raises(Exception):
        ValidationConfig(project_root="/tmp",horizons=(20,)).validate()


def test_cross_section_tail_is_contemporaneous_not_full_period():
    rows=[]
    for day in ["2020-01-03","2020-01-10"]:
        for i in range(100):
            rows.append({"symbol":f"S{i:03d}","as_of":pd.Timestamp(day),"horizon":20,"probability_up":i/100,"fwd_ret_20":0.01})
    d=pd.DataFrame(rows)
    s=_select_cross_section(d,20,0.01,"LONG")
    assert len(s)==2
    assert s.groupby("as_of").size().eq(1).all()
    assert set(s.symbol)=={"S099"}


def test_primary_gate_pass_and_fail_are_deterministic():
    metrics={
        "n":1000,"unique_symbols":200,"selection_dates":200,"win_rate":0.63,"validation_baseline_win_rate":0.55,"win_rate_edge_vs_validation_baseline":0.08,
        "mean_return":0.02,"median_return":0.015,"positive_years":5,"years_observed":5,"barrier_resolved_n":900,"barrier_win_rate":0.60,"barrier_expectancy_r":0.40,
        "largest_symbol_abs_contribution_fraction":0.03,"top10_symbol_abs_contribution_fraction":0.20,
    }
    tails=pd.DataFrame([
        {"horizon":20,"direction":"LONG","tail_fraction":0.01,"win_rate":0.63},
        {"horizon":20,"direction":"LONG","tail_fraction":0.05,"win_rate":0.61},
    ])
    gates,verdict=_evaluate_primary_gates(metrics,tails)
    assert verdict=="PASS" and all(gates.values())
    metrics["win_rate"]=0.55
    gates,verdict=_evaluate_primary_gates(metrics,tails)
    assert verdict=="FAIL" and gates["minimum_win_rate"] is False
