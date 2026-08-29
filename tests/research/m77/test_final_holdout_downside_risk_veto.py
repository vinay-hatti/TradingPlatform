from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import numpy as np

from trading_ai.research.m77.final_holdout_downside_risk_veto import (
    FinalHoldoutVetoConfig, PRIMARY_POPULATION, build_preregistration,
    _extract_final_candidate, _select_tail, evaluate_gates,
)


def test_preregistration_is_frozen_primary():
    p=build_preregistration()
    assert p['primary_population']==PRIMARY_POPULATION
    assert p['primary_horizon_sessions']==20
    assert p['tail_fraction']==0.01
    assert p['final_holdout_window']['start']=='2023-01-01'
    assert p['governance']['consumed_validation_read'] is False
    assert p['governance']['secondary_configuration_can_rescue_primary_failure'] is False
    assert len(p['preregistration_sha256'])==64


def test_config_rejects_mutation():
    c=FinalHoldoutVetoConfig(project_root='.', max_features=79)
    try:
        c.validate()
    except Exception:
        return
    raise AssertionError('mutation must fail closed')


def test_extract_final_candidate_trade_builder_ready():
    obj={'symbol':'ABC','as_of':'2024-05-03','profile':{'direction':'BULLISH','scores':{'overall':81},'trade_plan':{'certification':{'status':'PASS','trade_builder_ready':True}}}}
    r=_extract_final_candidate(obj)
    assert r is not None and r[PRIMARY_POPULATION] is True
    assert _extract_final_candidate({**obj,'as_of':'2022-12-30'}) is None


def test_select_tail_is_contemporaneous():
    rows=[]
    for d in ['2024-01-05','2024-01-12']:
        for i in range(200): rows.append({'symbol':f'S{i:03d}','as_of':pd.Timestamp(d),'probability_up':i/200})
    t=_select_tail(pd.DataFrame(rows))
    assert len(t)==4
    assert t.groupby('as_of').size().eq(2).all()


def good_metrics():
    return {'candidate_n':2000,'veto_n':60,'veto_symbols':40,'severe_loss_capture_lift_vs_random':2.5,'loss_10_rate_reduction':0.002,
            'mean_return_improvement':0.0,'win_rate_improvement':0.0,'vetoed_loss_10_rate':0.12,'baseline_loss_10_rate':0.06,
            'positive_risk_improvement_year_fraction':0.75}


def test_gates_pass_only_when_all_primary_requirements_pass():
    g,v=evaluate_gates(good_metrics())
    assert v=='PASS' and all(g.values())
    m=good_metrics(); m['severe_loss_capture_lift_vs_random']=1.99
    g,v=evaluate_gates(m)
    assert v=='FAIL' and not g['minimum_severe_loss_capture_lift_vs_random']


def test_year_fraction_gate_is_frozen():
    m=good_metrics(); m['positive_risk_improvement_year_fraction']=0.50
    g,v=evaluate_gates(m)
    assert v=='FAIL' and not g['minimum_positive_risk_improvement_year_fraction']


def test_no_validation_path_in_defaults():
    c=FinalHoldoutVetoConfig(project_root='.')
    for x in [c.development_panel,c.final_feature_root,c.raw_daily_root,c.pit_profiles_root,c.upstream_root,c.output_root]:
        assert 'm77_21_3' not in x.lower()
        assert 'validation' not in x.lower()


def test_evaluate_primary_attaches_frozen_horizon_before_integrity(monkeypatch, tmp_path):
    import trading_ai.research.m77.final_holdout_downside_risk_veto as mod
    seen = {}
    def fake_integrity(frame, raw_root):
        seen["horizons"] = frame["horizon"].tolist()
        return pd.DataFrame({
            "prediction_index": frame["prediction_index"],
            "raw_authority_present": True,
            "interval_integrity_clean": True,
            "source_return_matches_raw": True,
        })
    monkeypatch.setattr(mod, "_final_holdout_integrity", fake_integrity)
    pred = pd.DataFrame({
        "symbol": ["AAA", "BBB"],
        "as_of": pd.to_datetime(["2024-01-05", "2024-01-05"]),
        "fwd_ret_20": [0.05, -0.12],
        "probability_up": [0.9, 0.1],
    })
    authority = pd.DataFrame({
        "symbol": ["AAA", "BBB"],
        "as_of": pd.to_datetime(["2024-01-05", "2024-01-05"]),
        PRIMARY_POPULATION: [True, True],
    })
    mod.evaluate_primary(pred, authority, tmp_path)
    assert seen["horizons"] == [20, 20]


def test_evaluate_primary_rejects_mutated_horizon(monkeypatch, tmp_path):
    import trading_ai.research.m77.final_holdout_downside_risk_veto as mod
    pred = pd.DataFrame({
        "symbol": ["AAA"],
        "as_of": pd.to_datetime(["2024-01-05"]),
        "fwd_ret_20": [0.05],
        "probability_up": [0.9],
        "horizon": [30],
    })
    authority = pd.DataFrame({
        "symbol": ["AAA"],
        "as_of": pd.to_datetime(["2024-01-05"]),
        PRIMARY_POPULATION: [True],
    })
    try:
        mod.evaluate_primary(pred, authority, tmp_path)
    except Exception as exc:
        assert "horizon" in str(exc).lower()
        return
    raise AssertionError("mutated Final Holdout horizon must fail closed")


def test_evaluate_primary_missing_integrity_columns_fails_closed_without_scalar_bool(monkeypatch, tmp_path):
    import trading_ai.research.m77.final_holdout_downside_risk_veto as mod
    def fake_integrity(frame, raw_root):
        # Reproduces the prior failure class: helper returns no expected flags.
        return pd.DataFrame({"prediction_index": frame["prediction_index"]})
    monkeypatch.setattr(mod, "_final_holdout_integrity", fake_integrity)
    pred = pd.DataFrame({
        "symbol": ["AAA", "BBB"],
        "as_of": pd.to_datetime(["2024-01-05", "2024-01-05"]),
        "fwd_ret_20": [0.05, -0.12],
        "probability_up": [0.9, 0.1],
    })
    authority = pd.DataFrame({
        "symbol": ["AAA", "BBB"],
        "as_of": pd.to_datetime(["2024-01-05", "2024-01-05"]),
        PRIMARY_POPULATION: [True, True],
    })
    metrics, years, annotated = mod.evaluate_primary(pred, authority, tmp_path)
    assert annotated["integrity_clean_strict"].eq(False).all()
    assert metrics["candidate_n"] == 0


def test_final_holdout_integrity_accepts_2024_interval_and_does_not_use_validation_boundary(tmp_path):
    import trading_ai.research.m77.final_holdout_downside_risk_veto as mod
    raw = tmp_path / "raw"
    raw.mkdir()
    dates = pd.bdate_range("2023-10-02", "2024-03-29")
    close = pd.Series(np.linspace(100.0, 120.0, len(dates)))
    bars = pd.DataFrame({
        "session_date": dates,
        "open": close,
        "high": close * 1.001,
        "low": close * 0.999,
        "close": close,
        "volume": 1000000,
    })
    bars.to_csv(raw / "AAA.daily.csv.gz", index=False, compression="gzip")
    asof = pd.Timestamp("2024-01-05")
    i = int(np.where(dates == asof)[0][0])
    fwd = float(close.iloc[i+20] / close.iloc[i] - 1.0)
    pred = pd.DataFrame({
        "prediction_index": [0],
        "symbol": ["AAA"],
        "as_of": [asof],
        "horizon": [20],
        "fwd_ret_20": [fwd],
    })
    evidence = mod._final_holdout_integrity(pred, raw)
    assert len(evidence) == 1
    assert bool(evidence.iloc[0]["raw_authority_present"]) is True
    assert bool(evidence.iloc[0]["source_return_matches_raw"]) is True
    assert bool(evidence.iloc[0]["interval_integrity_clean"]) is True
