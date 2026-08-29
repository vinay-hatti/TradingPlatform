import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.serial_dependence_path_smoothness import (
    STATES, PathSmoothnessConfig, PathSmoothnessError,
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
    a["ret_autocorr_20"]=-.45+.10*i
    a["up_day_fraction_20"]=.25+.05*i
    a["down_day_fraction_20"]=.75-.05*i
    a["mom_accel_5_20"]=-.20+.05*i
    a["mom_accel_20_60"]=-.10+.03*i
    a["px_ret_5"]=-.05+.015*i
    a["px_ret_20"]=-.10+.025*i
    a["px_ret_60"]=-.12+.03*i
    return a

def test_feature_join_complete(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    p,m=load_panel(PathSmoothnessConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    assert len(p)==len(e)
    assert m["feature_join_missing_rows"]==0

def test_post_2017_rejected(tmp_path):
    e=_exec_panel();e.loc[0,"as_of"]="2018-01-02";ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    with pytest.raises(PathSmoothnessError):
        load_panel(PathSmoothnessConfig(
            project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
        ))

def test_all_frozen_states_materialize(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    p,_=load_panel(PathSmoothnessConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    for state in STATES:
        m=_state_mask(p,state)
        assert len(m)==len(p)
        assert m.dtype==bool

def test_evidence_contains_complement_nonoverlap_time_stability(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    p,_=load_panel(PathSmoothnessConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    ev,y,mo=evaluate_states(p)
    assert len(ev)==len(STATES)
    assert "mean_r_uplift_vs_complement" in ev.columns
    assert "nonoverlap_mean_r" in ev.columns
    assert not y.empty and not mo.empty

def test_smooth_and_choppy_positive_paths_are_distinct(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    p,_=load_panel(PathSmoothnessConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    smooth=_state_mask(p,"SMOOTH_POSITIVE_PATH")
    choppy=_state_mask(p,"CHOPPY_POSITIVE_PATH")
    assert not (smooth & choppy).any()

def test_readiness_explicit():
    ev=pd.DataFrame([{
        "state":"X","n":2000,"symbols":300,"mean_r":.3,"profit_factor":1.6,
        "equal_symbol_mean_r":.2,"top10_abs_contribution_fraction":.1,
        "mean_r_uplift_vs_complement":.1,"nonoverlap_mean_r":.2,
        "nonoverlap_profit_factor":1.4
    }])
    y=pd.DataFrame([{"state":"X","year":y,"mean_r":.3,"mean_r_uplift_vs_complement":.1} for y in range(2008,2018)])
    mo=pd.DataFrame([{"state":"X","month":f"2017-{m:02d}","mean_r":.3,"mean_r_uplift_vs_complement":.1} for m in range(1,13)])
    r=build_readiness(ev,y,mo)
    assert bool(r.iloc[0]["development_ready_path_state"])

def test_missing_feature_parity_fails_closed(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();a.loc[0,"ret_autocorr_20"]=np.nan
    ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    with pytest.raises(PathSmoothnessError,match="feature parity failed"):
        load_panel(PathSmoothnessConfig(
            project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
        ))
