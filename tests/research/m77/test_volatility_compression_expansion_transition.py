import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.volatility_compression_expansion_transition import (
    TRANSITION_STATES, VolatilityTransitionConfig, VolatilityTransitionError,
    _state_mask, build_readiness, evaluate_states, load_panel
)

def _exec_panel():
    rows=[]
    for d in pd.bdate_range("2015-01-05",periods=30):
        for i in range(10):
            rows.append({
                "symbol":f"S{i}","as_of":d,"entry_date":d+pd.offsets.BDay(1),
                "horizon":60,"target_atr":5.0,"stop_atr":3.0,
                "r_multiple":-.2+.05*i,"exit_day":25+i%4
            })
    return pd.DataFrame(rows)

def _authority():
    e=_exec_panel()
    a=e[["symbol","as_of"]].copy()
    i=np.tile(np.arange(10),30)
    a["rv_10"]=.10+.01*i
    a["rv_20"]=.15+.008*i
    a["rv_60"]=.20+.005*i
    a["range_atr"]=.5+.05*i
    return a

def test_feature_authority_join_complete(tmp_path):
    e=_exec_panel()
    ep=tmp_path/"exec.csv.gz"; e.to_csv(ep,index=False,compression="gzip")
    a=_authority()
    ap=tmp_path/"panel.pkl.gz"; a.to_pickle(ap,compression="gzip",protocol=5)
    p,m=load_panel(VolatilityTransitionConfig(
        project_root=str(tmp_path), executable_panel_path=str(ep), feature_authority_path=str(ap)
    ))
    assert m["feature_join_missing_rows"]==0
    assert len(p)==len(e)
    assert p[["rv_10","rv_20","rv_60","range_atr"]].notna().all().all()

def test_post_2017_rejected(tmp_path):
    e=_exec_panel();e.loc[0,"as_of"]="2018-01-02"
    ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    with pytest.raises(VolatilityTransitionError):
        load_panel(VolatilityTransitionConfig(
            project_root=str(tmp_path), executable_panel_path=str(ep), feature_authority_path=str(ap)
        ))

def test_all_frozen_transition_states_materialize(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    p,_=load_panel(VolatilityTransitionConfig(
        project_root=str(tmp_path), executable_panel_path=str(ep), feature_authority_path=str(ap)
    ))
    for s in TRANSITION_STATES:
        m=_state_mask(p,s)
        assert len(m)==len(p)
        assert m.dtype==bool

def test_evidence_has_complement_nonoverlap_and_year_month(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    p,_=load_panel(VolatilityTransitionConfig(
        project_root=str(tmp_path), executable_panel_path=str(ep), feature_authority_path=str(ap)
    ))
    ev,y,mo=evaluate_states(p)
    assert len(ev)==len(TRANSITION_STATES)
    assert "mean_r_uplift_vs_complement" in ev.columns
    assert "nonoverlap_mean_r" in ev.columns
    assert not y.empty and not mo.empty

def test_readiness_is_frozen_and_explicit():
    ev=pd.DataFrame([{
        "state":"X","n":2000,"symbols":300,"mean_r":.3,"profit_factor":1.6,
        "equal_symbol_mean_r":.2,"top10_abs_contribution_fraction":.1,
        "mean_r_uplift_vs_complement":.1,"nonoverlap_mean_r":.2,
        "nonoverlap_profit_factor":1.4
    }])
    y=pd.DataFrame([{"state":"X","year":y,"mean_r":.3,"mean_r_uplift_vs_complement":.1} for y in range(2008,2018)])
    mo=pd.DataFrame([{"state":"X","month":f"2017-{m:02d}","mean_r":.3,"mean_r_uplift_vs_complement":.1} for m in range(1,13)])
    r=build_readiness(ev,y,mo)
    assert bool(r.iloc[0]["development_ready_transition_state"])

def test_missing_feature_parity_fails_closed(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority().iloc[:-1];ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    with pytest.raises(VolatilityTransitionError,match="feature parity failed"):
        load_panel(VolatilityTransitionConfig(
            project_root=str(tmp_path), executable_panel_path=str(ep), feature_authority_path=str(ap)
        ))
