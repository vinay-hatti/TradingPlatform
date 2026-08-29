import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.edge_interaction_necessity_redundancy import (
    EdgeDecompositionConfig, EdgeDecompositionError, add_selection_states,
    attribution_summary, management_decomposition, selection_decomposition, load_authority
)

def _panel():
    rows=[]
    dates=pd.bdate_range("2015-01-05",periods=20)
    for di,d in enumerate(dates):
        for i in range(10):
            for target in (3.0,5.0):
                rows.append({
                    "symbol":f"S{i}","as_of":d,"entry_date":d+pd.offsets.BDay(1),
                    "horizon":60,"target_atr":target,"stop_atr":3.0,
                    "r_multiple":(-.5+.15*i)+(0.15 if target==5.0 and i>=7 else 0),
                    "exit_day":20+i%5,
                    "probability_up":.45+.04*i,
                    "bearish_rank_pct":.90-.08*i,
                    "overall_score":.35+.05*i,
                    "idi_trade_quality":.30+.055*i,
                    "score_options_suitability":.25+.06*i,
                })
    return pd.DataFrame(rows)

def test_load_authority_complete(tmp_path):
    p=_panel();ep=tmp_path/"exec.csv.gz";p.to_csv(ep,index=False,compression="gzip")
    out,m=load_authority(EdgeDecompositionConfig(project_root=str(tmp_path),executable_panel_path=str(ep)))
    assert len(out)==len(p)
    assert m["consumed_2018_2026_rows_read"]==0

def test_post_2017_rejected(tmp_path):
    p=_panel();p.loc[0,"as_of"]="2018-01-02";ep=tmp_path/"exec.csv.gz";p.to_csv(ep,index=False,compression="gzip")
    with pytest.raises(EdgeDecompositionError):
        load_authority(EdgeDecompositionConfig(project_root=str(tmp_path),executable_panel_path=str(ep)))

def test_top3_is_subset_of_probability_top20_when_cohort_sufficient():
    p=_panel()
    cert=p[p["target_atr"]==5.0].copy()
    x=add_selection_states(cert)
    assert not ((x["capital_top3"]) & (~x["prob_top20"])).any()

def test_selection_decomposition_reports_redundancy():
    p=_panel()
    cert=p[p["target_atr"]==5.0].copy()
    s,r=selection_decomposition(cert)
    assert "CAPITAL_PRIORITY_TOP3" in set(s["cohort"])
    assert bool(r.iloc[0]["right_subset_of_left"])

def test_management_counterfactual_is_exact_matched():
    p=_panel()
    cert=p[p["target_atr"]==5.0].copy()
    m=management_decomposition(p,cert)
    assert set(m["cohort"])=={"ALL_MATCHED","PROBABILITY_UP_TOP20","CAPITAL_PRIORITY_TOP3"}
    assert (m["matched_n"]>0).all()

def test_drve_nonidentifiability_is_explicit():
    p=_panel();cert=p[p["target_atr"]==5.0].copy()
    s,r=selection_decomposition(cert)
    m=management_decomposition(p,cert)
    a=attribution_summary(s,m,r)
    assert a["drve_necessity_identifiable"] is False
    assert "post-DRVE" in a["drve_necessity_reason"]

def test_missing_neutral_geometry_fails_closed():
    p=_panel()
    p=p[p["target_atr"]==5.0].copy()
    cert=p.copy()
    with pytest.raises(EdgeDecompositionError,match="Frozen geometry unavailable"):
        management_decomposition(p,cert)
