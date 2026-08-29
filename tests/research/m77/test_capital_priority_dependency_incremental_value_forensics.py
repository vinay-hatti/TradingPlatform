import pandas as pd
import numpy as np

from trading_ai.research.m77.capital_priority_dependency_incremental_value_forensics import (
    annotate, date_subset_forensics, cohort_size_conditioned_effect
)

def _panel():
    rows=[]
    for di,d in enumerate(pd.bdate_range("2016-01-04",periods=20)):
        n=4 if di<5 else (8 if di<10 else (15 if di<15 else 30))
        for i in range(n):
            rows.append({
                "symbol":f"S{i}",
                "as_of":d,
                "entry_date":d+pd.offsets.BDay(1),
                "probability_up":0.50+0.01*i,
                "r_multiple":-0.2+0.03*i,
            })
    return pd.DataFrame(rows)

def test_cpre_is_definitionally_probability_ranked():
    x=annotate(_panel())
    top3=x[x["capital_top3"]]
    assert (top3["probability_rank"]<=3).all()

def test_subset_can_fail_for_small_cohorts():
    x=annotate(_panel())
    d=date_subset_forensics(x)
    assert (~d["top3_subset_of_top20"]).any()

def test_subset_fraction_is_explicit():
    x=annotate(_panel())
    d=date_subset_forensics(x)
    f=float(d["top3_subset_of_top20"].mean())
    assert 0.0 <= f <= 1.0

def test_divergence_is_explained_by_cohort_size():
    x=annotate(_panel())
    d=date_subset_forensics(x)
    div=d[~d["top3_subset_of_top20"]]
    assert not div.empty
    assert div["cohort_n"].min()<=8

def test_conditioned_effect_has_frozen_strata():
    x=annotate(_panel())
    strata,summary=cohort_size_conditioned_effect(x)
    assert not strata.empty
    assert "cohort_size_strata_weighted_top3_minus_top20_r" in summary
    assert set(strata["cohort_size_stratum"]).issubset({"01_05","06_10","11_20","21_50","51_PLUS"})

def test_no_new_thresholds_are_needed_for_forensics():
    x=annotate(_panel())
    assert "prob_top20" in x.columns
    assert "capital_top3" in x.columns
