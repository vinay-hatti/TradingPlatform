from __future__ import annotations

import csv
import gzip
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.edge_discovery_lab import (
    EdgeLabError,
    LabConfig,
    add_forward_outcomes,
    chronological_partitions,
    engineer_ohlcv_features,
    ml_hypothesis_generation,
    read_daily_file,
    run_lab,
    sanitize_nonfinite_numeric,
)


def _bars(n: int = 900) -> pd.DataFrame:
    dates = pd.bdate_range("2004-01-02", periods=n)
    rng = np.random.default_rng(77)
    rets = rng.normal(0.0004, 0.012, n)
    close = 100 * np.exp(np.cumsum(rets))
    open_ = close * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.015, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.015, n))
    volume = rng.integers(100_000, 2_000_000, n)
    return pd.DataFrame({"session_date": dates, "open": open_, "high": high, "low": low, "close": close, "volume": volume})


def _write_daily(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression="gzip")


def test_feature_engineering_uses_past_only_shape():
    df = _bars(350).rename(columns={"session_date": "as_of"})
    out = engineer_ohlcv_features(df)
    assert "rsi_14" in out
    assert "dist_sma_252" in out
    assert "breakout_high_20" in out
    assert out.loc[:100, "px_ret_20"].notna().any()


def test_forward_outcome_same_bar_ambiguity_is_nan():
    df = pd.DataFrame({
        "as_of": pd.bdate_range("2010-01-01", periods=4),
        "open": [100, 100, 100, 100],
        "high": [101, 103, 101, 101],
        "low": [99, 97, 99, 99],
        "close": [100, 100, 100, 100],
        "volume": [1000] * 4,
        "atr_14": [2.0] * 4,
    })
    out = add_forward_outcomes(df, [1], [(1.0, 1.0)])
    assert np.isnan(out.loc[0, "long_barrier_t1p0_s1p0_h1"])
    assert np.isnan(out.loc[0, "short_barrier_t1p0_s1p0_h1"])


def test_partitions_are_chronological():
    panel = pd.DataFrame({"as_of": pd.bdate_range("2005-01-01", periods=100)})
    p = chronological_partitions(panel)
    assert set(p) == {"DISCOVERY", "CONFIRMATION", "INTERNAL_HOLDOUT"}
    assert panel.loc[p == "DISCOVERY", "as_of"].max() < panel.loc[p == "CONFIRMATION", "as_of"].min()
    assert panel.loc[p == "CONFIRMATION", "as_of"].max() < panel.loc[p == "INTERNAL_HOLDOUT", "as_of"].min()


def test_dev_boundary_fail_closed(tmp_path: Path):
    cfg = LabConfig(
        project_root=str(tmp_path), daily_root="research_data/daily", feature_root=None,
        output_root="research_data/out", dev_end="2018-01-01",
    )
    with pytest.raises(EdgeLabError):
        cfg.validate()


def test_sealed_path_rejected(tmp_path: Path):
    cfg = LabConfig(
        project_root=str(tmp_path), daily_root="research_data/final_holdout/daily", feature_root=None,
        output_root="research_data/out", workers=1,
    )
    with pytest.raises(EdgeLabError):
        run_lab(cfg)


def test_end_to_end_small_synthetic(tmp_path: Path):
    root = tmp_path
    daily_root = root / "research_data" / "daily"
    for i, symbol in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]):
        df = _bars(900)
        # Introduce deterministic cross-sectional variation without future leakage.
        df["close"] *= 1 + i * 0.01
        df["open"] *= 1 + i * 0.01
        df["high"] *= 1 + i * 0.01
        df["low"] *= 1 + i * 0.01
        _write_daily(daily_root / f"{symbol}.daily.csv.gz", df)

    cfg = LabConfig(
        project_root=str(root), daily_root="research_data/daily", feature_root=None,
        output_root="research_data/m77_21_0/test_lab", cadence="weekly", workers=1,
        min_history=260, min_samples=50, horizons=(1, 5, 10),
        target_stop_geometries=((1.0, 1.0),), top_univariate=10,
        top_interaction_features=5, max_pair_candidates=20,
        include_certified_pit_features=False, include_ml_hypothesis_generation=False,
        bootstrap_samples=0,
    )
    summary = run_lab(cfg)
    out = root / "research_data" / "m77_21_0" / "test_lab"
    assert summary["status"] == "COMPLETE"
    assert summary["validation_partition_opened"] is False
    assert summary["final_holdout_opened"] is False
    assert (out / "edge_discovery_summary.json").exists()
    assert (out / "edge_registry.csv").exists()
    assert (out / "EDGE_DISCOVERY_REPORT.md").exists()
    assert (out / "stationarity_confounder_evidence.csv").exists()
    assert "stationarity_confounder_survivors" in summary


def test_nonfinite_numeric_values_are_sanitized():
    frame = pd.DataFrame({
        "finite": [1.0, 2.0, 3.0],
        "mixed": [1.0, np.inf, -np.inf],
        "label": ["a", "b", "c"],
    })
    out, counts = sanitize_nonfinite_numeric(frame)
    assert counts == {"mixed": 2}
    assert out["mixed"].isna().sum() == 2
    assert out["finite"].tolist() == [1.0, 2.0, 3.0]


def test_forward_outcomes_do_not_emit_fragmentation_warning():
    df = _bars(400).rename(columns={"session_date": "as_of"})
    df = engineer_ohlcv_features(df)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        add_forward_outcomes(df, [1, 2, 3, 5, 10], [(1.0, 1.0), (1.5, 1.0), (2.0, 1.0)])
    assert not any("highly fragmented" in str(w.message).lower() for w in captured)


def test_ml_boundary_sanitizes_infinities():
    rng = np.random.default_rng(7701)
    n_disc, n_conf = 2200, 600
    n = n_disc + n_conf
    signal = rng.normal(size=n)
    noisy = rng.normal(size=n)
    # Reproduce the production failure class: explicit +/-inf in otherwise
    # useful numeric features reaching the ML stage.
    noisy[50] = np.inf
    noisy[100] = -np.inf
    frame = pd.DataFrame({
        "partition": ["DISCOVERY"] * n_disc + ["CONFIRMATION"] * n_conf,
        "fwd_ret_1": 0.01 * signal + rng.normal(0, 0.01, n),
        "feature_signal": signal,
        "feature_nonfinite": noisy,
    })
    cfg = LabConfig(
        project_root=".", daily_root="research_data/daily", feature_root=None, output_root="research_data/out",
        horizons=(1,), include_ml_hypothesis_generation=True,
        include_certified_pit_features=False, workers=1, min_samples=50,
    )
    out = ml_hypothesis_generation(frame, cfg)
    assert not out.empty
    assert set(out.loc[out["model"].isin(["LOGISTIC_L2", "RANDOM_FOREST", "HIST_GRADIENT_BOOSTING"]), "model"]) == {
        "LOGISTIC_L2", "RANDOM_FOREST", "HIST_GRADIENT_BOOSTING"
    }

from trading_ai.research.m77.edge_discovery_lab import (
    candidate_key,
    build_edge_registry,
    robustness_destruction_tests,
    stationarity_confounder_tests,
)


def test_candidate_key_distinguishes_ranges():
    a = pd.Series({"candidate_type":"NUMERIC_BIN","feature":"vwap","operator":"RANGE","lower":1.0,"upper":5.0,"value":np.nan,"direction":"LONG","horizon":60})
    b = a.copy(); b["lower"], b["upper"] = 5.0, 10.0
    assert candidate_key(a) != candidate_key(b)


def test_registry_does_not_cross_attach_robustness_between_ranges():
    base = {"candidate_type":"NUMERIC_BIN","feature":"vwap","operator":"RANGE","value":np.nan,"direction":"LONG","horizon":60,
            "robust_pass":True,"holdout_mean_return_edge":0.02,"holdout_win_rate_edge":0.03,"confirm_mean_return_edge":0.01}
    a={**base,"lower":1.0,"upper":5.0}; b={**base,"lower":5.0,"upper":10.0}
    validated=pd.DataFrame([a,b])
    ra={**a,"candidate_key":candidate_key(pd.Series(a)),"destruction_pass":True}
    rb={**b,"candidate_key":candidate_key(pd.Series(b)),"destruction_pass":False}
    cfg=LabConfig(project_root=".",daily_root="research_data/d",feature_root=None,output_root="research_data/o")
    reg=build_edge_registry(validated,pd.DataFrame(),pd.DataFrame(),pd.DataFrame(),pd.DataFrame([ra,rb]),cfg)
    got={tuple(x): bool(y) for x,y in zip(reg[["lower","upper"]].to_numpy(),reg["destruction_pass"])}
    assert got[(1.0,5.0)] is True
    assert got[(5.0,10.0)] is False


def test_stationarity_confounder_reports_exact_candidate_identity():
    dates=pd.bdate_range("2014-01-01",periods=300)
    rows=[]
    for s in [f"S{i:02d}" for i in range(25)]:
        for d in dates:
            rows.append({"symbol":s,"as_of":d,"partition":"INTERNAL_HOLDOUT","calendar_year":d.year,"close":20.0,"vwap":7.0,"fwd_ret_20":0.01})
    panel=pd.DataFrame(rows)
    rec=pd.DataFrame([{"candidate_type":"NUMERIC_BIN","feature":"vwap","operator":"RANGE","lower":5.0,"upper":10.0,"value":np.nan,"direction":"LONG","horizon":20,"robust_pass":True}])
    cfg=LabConfig(project_root=".",daily_root="research_data/d",feature_root=None,output_root="research_data/o",min_samples=50)
    out=stationarity_confounder_tests(panel,rec,cfg)
    assert len(out)==1
    assert out.iloc[0]["candidate_key"] == candidate_key(rec.iloc[0])
    assert out.iloc[0]["unique_symbols"] == 25


def test_run_lab_defines_stationarity_even_when_no_evidence(tmp_path: Path, monkeypatch):
    root = tmp_path
    daily_root = root / "research_data" / "daily"
    for i, symbol in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]):
        df = _bars(900)
        df[["open","high","low","close"]] *= 1 + i * 0.01
        _write_daily(daily_root / f"{symbol}.daily.csv.gz", df)
    import trading_ai.research.m77.edge_discovery_lab as lab
    monkeypatch.setattr(lab, "stationarity_confounder_tests", lambda panel, validated, cfg: pd.DataFrame())
    cfg = LabConfig(project_root=str(root), daily_root="research_data/daily", feature_root=None,
        output_root="research_data/m77_21_0/test_empty_stationarity", cadence="weekly", workers=1,
        min_history=260, min_samples=50, horizons=(1,), target_stop_geometries=((1.0,1.0),),
        top_univariate=5, top_interaction_features=3, max_pair_candidates=5,
        include_certified_pit_features=False, include_ml_hypothesis_generation=False, bootstrap_samples=0)
    summary = lab.run_lab(cfg)
    assert summary["status"] == "COMPLETE"
    assert summary["stationarity_confounder_survivors"] == 0
