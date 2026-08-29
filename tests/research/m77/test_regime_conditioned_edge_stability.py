import numpy as np
import pandas as pd

from trading_ai.research.m77.regime_conditioned_edge_stability import (
    REGIME_FAMILIES,
    RegimeStabilityConfig,
    _prior_quantile_buckets,
    build_regime_calendar,
    overall_stability,
    regime_evidence,
    regime_readiness,
)


def _panel():
    rng = np.random.default_rng(7728)
    rows = []
    symbols = [f"S{i:03d}" for i in range(150)]
    dates = pd.bdate_range("2008-01-02", periods=650)
    for di, d in enumerate(dates):
        regime = np.sin(di / 40.0)
        for i, s in enumerate(symbols):
            q = (i + 1) / len(symbols)
            # top probability cohort has persistent but regime-varying uplift
            edge = 0.14 if q >= 0.80 else 0.02
            r = edge + 0.04 * regime + rng.normal(0, 0.18)
            rows.append({
                "symbol": s,
                "as_of": d,
                "entry_date": d + pd.Timedelta(days=1),
                "r_multiple": r,
                "exit_type": "TIME",
                "probability_up": q + 0.015 * regime,
                "bearish_rank_pct": q,
                "overall_score": 50 + 50 * q,
                "idi_trade_quality": 40 + 60 * q,
                "score_options_suitability": 45 + 55 * q,
                "px_ret_5": q - 0.5 + 0.1 * regime,
                "dist_sma_20": q - 0.5 + 0.12 * regime,
                "atr_pct_14": 0.01 + 0.015 * q + 0.006 * (1 - regime),
            })
    p = pd.DataFrame(rows)
    p["calendar_year"] = p["as_of"].dt.year
    p["rank_probability_up"] = p.groupby("as_of")["probability_up"].rank(method="average", pct=True)
    return p


def test_regime_catalog_is_frozen():
    assert REGIME_FAMILIES == (
        "VOLATILITY", "TREND_BREADTH", "MOMENTUM_BREADTH", "PROBABILITY_LEVEL",
        "PROBABILITY_DISPERSION", "COMPOSITE", "CALENDAR",
    )


def test_prior_quantile_bucket_does_not_use_current_or_future_value():
    d = pd.DataFrame({"x": np.arange(20, dtype=float)})
    a = _prior_quantile_buckets(d, "x", "L", "M", "H", min_prior=5, lookback=10)
    d2 = d.copy()
    d2.loc[10:, "x"] = 1e9
    b = _prior_quantile_buckets(d2, "x", "L", "M", "H", min_prior=5, lookback=10)
    assert a.iloc[9] == b.iloc[9]


def test_build_regime_calendar_uses_only_development_dates():
    p = _panel()
    cfg = RegimeStabilityConfig(project_root=".", min_prior_regime_dates=20, regime_lookback_dates=80)
    c = build_regime_calendar(p, cfg)
    assert c["as_of"].max() <= pd.Timestamp("2017-12-31")
    assert c["VOLATILITY"].notna().sum() > 0
    assert c["TREND_BREADTH"].notna().sum() > 0
    assert set(c["CALENDAR"].unique()) <= {"Q1", "Q2", "Q3", "Q4"}


def test_regime_evidence_detects_persistent_top20_edge():
    p = _panel()
    cfg = RegimeStabilityConfig(project_root=".", min_prior_regime_dates=20, regime_lookback_dates=80)
    c = build_regime_calendar(p, cfg)
    e, y = regime_evidence(p, c)
    assert not e.empty and not y.empty
    adequate = e[e["selected_n"] >= 350]
    assert (adequate["interaction_mean_r_uplift"] > 0).mean() > 0.7


def test_readiness_and_overall_stability_are_fail_closed():
    rows = []
    years = []
    for fam in REGIME_FAMILIES:
        for state in ("A", "B"):
            rows.append({
                "regime_family": fam, "regime_state": state,
                "population_n": 5000, "population_symbols": 300,
                "selected_n": 1000, "selected_symbols": 200,
                "selected_mean_r": .20, "selected_median_r": .10, "selected_win_rate": .55,
                "selected_profit_factor": 1.4, "selected_equal_symbol_mean_r": .15,
                "selected_positive_symbol_fraction": .70, "selected_gap_stop_fraction": .05,
                "selected_tail_1pct_r": -1.5, "selected_top10_abs_contribution_fraction": .20,
                "complement_n": 4000, "complement_symbols": 300,
                "complement_mean_r": .10, "complement_profit_factor": 1.2, "complement_win_rate": .51,
                "interaction_mean_r_uplift": .10, "interaction_profit_factor_uplift": .20,
                "interaction_win_rate_uplift": .04,
                "nonoverlap_selected_mean_r": .15, "nonoverlap_selected_profit_factor": 1.3,
            })
            for yr in range(2008, 2018):
                years.append({
                    "regime_family": fam, "regime_state": state, "year": yr,
                    "population_n": 500, "selected_n": 100,
                    "interaction_mean_r_uplift": .08, "interaction_profit_factor_uplift": .15,
                })
    r, f = regime_readiness(pd.DataFrame(rows), pd.DataFrame(years))
    assert r["regime_supports_interaction"].all()
    o = overall_stability(f)
    assert o["development_regime_stability_verdict"] == "READY_FOR_REVIEW"


def test_family_instability_prevents_ready_verdict():
    f = pd.DataFrame([
        {"regime_family": x, "states_with_adequate_sample": 2, "states_supporting_interaction": 2,
         "support_fraction": 1.0, "family_stable": True}
        for x in REGIME_FAMILIES
    ])
    f.loc[f["regime_family"] == "VOLATILITY", ["states_supporting_interaction", "support_fraction", "family_stable"]] = [0, 0.0, False]
    f.loc[f["regime_family"] == "TREND_BREADTH", ["states_supporting_interaction", "support_fraction", "family_stable"]] = [0, 0.0, False]
    o = overall_stability(f)
    assert o["development_regime_stability_verdict"] == "NOT_STABLE_ENOUGH"
