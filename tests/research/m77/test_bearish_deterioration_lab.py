from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.bearish_deterioration_lab import (
    BearishResearchConfig,
    _avoidance_evidence,
    _candidate_stats,
    _partition,
    _select_tail,
    _tail_evidence,
)


def _pred() -> pd.DataFrame:
    rows=[]
    for year in range(2008,2018):
        for wk in range(1,5):
            day=pd.Timestamp(year,1,1)+pd.Timedelta(days=7*wk)
            for i in range(100):
                p=i/100
                ret=-0.12 if i < 5 else (0.02 if i > 50 else -0.005)
                rows.append({"symbol":f"S{i:03d}","as_of":day,"horizon":20,"probability_up":p,"fwd_ret_20":ret,"test_year":year})
    return pd.DataFrame(rows)


def test_config_blocks_validation_and_final_holdout_sources():
    BearishResearchConfig(project_root="/tmp").validate()
    with pytest.raises(Exception):
        BearishResearchConfig(project_root="/tmp", development_predictions="research_data/m77_21_3/validation_predictions.csv.gz").validate()
    with pytest.raises(Exception):
        BearishResearchConfig(project_root="/tmp", development_panel="final_holdout/panel.pkl.gz").validate()


def test_partition_is_development_only():
    s=pd.Series([2008,2011,2014,2017,2018])
    got=_partition(s).tolist()
    assert got==["DISCOVERY","CONFIRMATION","INTERNAL_HOLDOUT","INTERNAL_HOLDOUT","OUTSIDE"]


def test_tail_selection_is_contemporaneous():
    d=_pred()
    s=_select_tail(d,20,0.01)
    assert s.groupby("as_of").size().eq(1).all()
    assert set(s.symbol)=={"S000"}


def test_bearish_tail_detects_downside_edge():
    ev=_tail_evidence(_pred())
    r=ev[(ev.horizon==20)&(ev.tail_fraction==0.05)].iloc[0]
    assert r.short_win_rate > 0.95
    assert r.short_win_rate_edge > 0.30
    assert r.mean_signed_return > 0


def test_avoidance_filter_reduces_severe_long_losses():
    ev=_avoidance_evidence(_pred())
    r=ev[(ev.horizon==20)&(ev.tail_fraction_excluded==0.05)].iloc[0]
    assert r.severe_loss_rate_reduction > 0
    assert r.retained_long_loss_rate < r.baseline_long_loss_rate


def test_candidate_stats_uses_breadth_and_concentration():
    d=_pred()
    d["rank__x"]=d.groupby("as_of")["probability_up"].rank(pct=True)
    spec={"conditions":[{"column":"rank__x","op":"LE","value":0.05}]}
    s=_candidate_stats(d,20,spec)
    assert s is not None
    assert s["short_win_rate"] > .95
    assert s["unique_symbols"] >= 5
    assert 0 <= s["top10_symbol_abs_contribution_fraction"] <= 1
