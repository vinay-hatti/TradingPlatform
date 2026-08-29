from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.positive_selection_edge_discovery import (
    PositiveSelectionConfig,
    PositiveSelectionError,
    _nonoverlap,
    readiness,
    selection_evidence,
    walk_forward_meta_scores,
)


def _panel():
    rows=[]
    rng=np.random.default_rng(7724)
    symbols=[f"S{i:03d}" for i in range(120)]
    for year in range(2008, 2018):
        for week in range(18):
            d=pd.Timestamp(f"{year}-01-05")+pd.Timedelta(days=7*week)
            for i,s in enumerate(symbols):
                quality=(i%20)/19
                prob=0.25+0.65*quality+0.02*rng.normal()
                ret=0.015*(quality-0.40)+0.02*rng.normal()
                rows.append({
                    "symbol":s,"as_of":d,"horizon":20,"calendar_year":year,
                    "probability_up":prob,"overall_score":50+40*quality,
                    "score_overall":50+40*quality,"score_bullish":40+50*quality,
                    "score_bearish":60-50*quality,"score_confidence":80,
                    "score_options_suitability":50+35*quality,
                    "idi_readiness":50+30*quality,"idi_trade_quality":45+45*quality,
                    "idi_capital_priority":50+30*quality,"profile_confidence":80,
                    "score_overall_rank_pct":quality,
                    "fwd_ret_20":ret,
                })
    return pd.DataFrame(rows)


def test_meta_scores_are_strictly_forward_and_seed_years_unscored():
    p=_panel()
    s=walk_forward_meta_scores(p,20,7724)
    assert s[p["calendar_year"]<=2010].isna().all()
    assert s[p["calendar_year"]>=2011].notna().all()


def test_selection_evidence_finds_positive_rank_signal():
    p=_panel()
    cfg=PositiveSelectionConfig(project_root="/tmp")
    e,y,s=selection_evidence(p,cfg)
    row=e[(e.selector=="PROBABILITY_UP")&(e.horizon==20)&(e.top_fraction==0.10)].iloc[0]
    assert row.selected_n>500
    assert row.win_rate_uplift>0
    assert row.mean_return_uplift>0
    assert not y.empty
    assert not s.empty


def test_nonoverlap_reduces_repeated_symbol_windows():
    p=pd.DataFrame({
        "symbol":["A","A","A"],"as_of":pd.to_datetime(["2014-01-03","2014-01-10","2014-02-28"]),
        "fwd_ret_20":[.1,.2,.3],
    })
    q=_nonoverlap(p,20)
    assert len(q)==2


def test_readiness_requires_all_gates():
    e=pd.DataFrame([{
        "horizon":20,"selector":"X","top_fraction":.1,"selected_n":1000,"selected_symbols":200,
        "win_rate_uplift":.03,"mean_return_uplift":.004,"loss_10_rate_change":-.01,
        "selected_equal_symbol_mean_return":.01,"selected_positive_symbol_fraction":.7,
        "nonoverlap_win_rate":.62,"baseline_win_rate":.58,
        "top10_symbol_abs_contribution_fraction":.2,
    }])
    years=pd.DataFrame([
        {"horizon":20,"selector":"X","top_fraction":.1,"win_rate_uplift":.01,"mean_return_uplift":.01}
        for _ in range(6)
    ]+[
        {"horizon":20,"selector":"X","top_fraction":.1,"win_rate_uplift":-.01,"mean_return_uplift":-.01}
    ])
    r=readiness(e,years)
    assert bool(r.iloc[0].development_ready)


def test_consumed_history_guard_is_explicit_in_source():
    src=Path(__file__).resolve().parents[3]/"src/trading_ai/research/m77/positive_selection_edge_discovery.py"
    text=src.read_text()
    assert "M77.24 refuses consumed history" in text
    assert "2018-01-01 through 2026-08-26" in text
    assert "prospective_certification_not_before" in text
