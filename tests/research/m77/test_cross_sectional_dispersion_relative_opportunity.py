import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.cross_sectional_dispersion_relative_opportunity import (
    DATE_STATES, DispersionOpportunityConfig, DispersionOpportunityError,
    _state_mask, build_readiness, evaluate_states, load_panel
)

def _exec_panel():
    rows=[]
    for di,d in enumerate(pd.bdate_range("2015-01-05",periods=30)):
        for i in range(10):
            rows.append({
                "symbol":f"S{i}","as_of":d,"entry_date":d+pd.offsets.BDay(1),
                "horizon":60,"target_atr":5.0,"stop_atr":3.0,
                "r_multiple":-.2+.05*i,"exit_day":25+i%4,
                "probability_up":.50+.02*i+.001*di,
                "overall_score":.40+.03*i+.002*(di%5),
            })
    return pd.DataFrame(rows)

def test_feature_join_complete(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    p,m=load_panel(DispersionOpportunityConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep)
    ))
    assert len(p)==len(e)
    assert m["feature_join_missing_rows"]==0
    assert m["dates"]==30

def test_post_2017_rejected(tmp_path):
    e=_exec_panel();e.loc[0,"as_of"]="2018-01-02";ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    with pytest.raises(DispersionOpportunityError):
        load_panel(DispersionOpportunityConfig(
            project_root=str(tmp_path),executable_panel_path=str(ep)
        ))

def test_all_frozen_date_states_materialize(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    p,_=load_panel(DispersionOpportunityConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep)
    ))
    for state in DATE_STATES:
        m=_state_mask(p,state)
        assert len(m)==len(p)
        assert m.dtype==bool

def test_evidence_contains_complement_nonoverlap_and_stability(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    p,_=load_panel(DispersionOpportunityConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep)
    ))
    ev,y,mo=evaluate_states(p)
    assert len(ev)==len(DATE_STATES)
    assert "mean_r_uplift_vs_complement" in ev.columns
    assert "nonoverlap_mean_r" in ev.columns
    assert not y.empty and not mo.empty

def test_date_level_state_is_constant_within_date(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    p,_=load_panel(DispersionOpportunityConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep)
    ))
    g=p.groupby("as_of")
    assert (g["probability_dispersion"].nunique()==1).all()
    assert (g["top_probability_margin"].nunique()==1).all()
    assert (g["probability_hhi"].nunique()==1).all()

def test_readiness_explicit():
    ev=pd.DataFrame([{
        "state":"X","n":3000,"symbols":300,"mean_r":.3,"profit_factor":1.6,
        "equal_symbol_mean_r":.2,"top10_abs_contribution_fraction":.1,
        "mean_r_uplift_vs_complement":.1,"nonoverlap_mean_r":.2,
        "nonoverlap_profit_factor":1.4
    }])
    y=pd.DataFrame([{"state":"X","year":y,"mean_r":.3,"mean_r_uplift_vs_complement":.1} for y in range(2008,2018)])
    mo=pd.DataFrame([{"state":"X","month":f"2017-{m:02d}","mean_r":.3,"mean_r_uplift_vs_complement":.1} for m in range(1,13)])
    r=build_readiness(ev,y,mo)
    assert bool(r.iloc[0]["development_ready_dispersion_state"])

def test_missing_feature_parity_fails_closed(tmp_path):
    e=_exec_panel()
    e.loc[0,"probability_up"]=np.nan
    ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    with pytest.raises(DispersionOpportunityError,match="opportunity-authority parity failed"):
        load_panel(DispersionOpportunityConfig(
            project_root=str(tmp_path),executable_panel_path=str(ep)
        ))

def test_binds_directly_to_executable_authority(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    p,m=load_panel(DispersionOpportunityConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep)
    ))
    assert m["opportunity_authority_source"]=="M77.26.1_EXECUTABLE_PANEL"
    assert m["opportunity_fields"]==["probability_up","overall_score"]
    assert m["opportunity_authority_missing_rows"]==0
    assert np.allclose(
        p.sort_values(["as_of","symbol"])["probability_up"].to_numpy(),
        e.sort_values(["as_of","symbol"])["probability_up"].to_numpy()
    )
