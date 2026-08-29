import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.outcome_asymmetry_conditional_tail_structure import (
    CONDITION_STATES, TailStructureConfig, TailStructureError,
    _state_mask, build_readiness, evaluate_states, load_panel
)

def _panel():
    rows=[]
    for di,d in enumerate(pd.bdate_range("2015-01-05",periods=40)):
        for i in range(10):
            rows.append({
                "symbol":f"S{i}","as_of":d,"entry_date":d+pd.offsets.BDay(1),
                "horizon":60,"target_atr":5.0,"stop_atr":3.0,"exit_day":25+i%4,
                "r_multiple":-2.0+0.5*i,
                "probability_up":.45+.04*i,
                "bearish_rank_pct":.90-.08*i,
                "overall_score":.35+.05*i,
                "idi_trade_quality":.30+.055*i,
                "score_options_suitability":.25+.06*i,
            })
    return pd.DataFrame(rows)

def test_load_complete(tmp_path):
    p=_panel();ep=tmp_path/"exec.csv.gz";p.to_csv(ep,index=False,compression="gzip")
    out,m=load_panel(TailStructureConfig(project_root=str(tmp_path),executable_panel_path=str(ep)))
    assert len(out)==len(p)
    assert m["condition_authority_missing_rows"]==0

def test_post_2017_rejected(tmp_path):
    p=_panel();p.loc[0,"as_of"]="2018-01-02";ep=tmp_path/"exec.csv.gz";p.to_csv(ep,index=False,compression="gzip")
    with pytest.raises(TailStructureError):
        load_panel(TailStructureConfig(project_root=str(tmp_path),executable_panel_path=str(ep)))

def test_all_states_materialize(tmp_path):
    p=_panel();ep=tmp_path/"exec.csv.gz";p.to_csv(ep,index=False,compression="gzip")
    out,_=load_panel(TailStructureConfig(project_root=str(tmp_path),executable_panel_path=str(ep)))
    for s in CONDITION_STATES:
        m=_state_mask(out,s)
        assert len(m)==len(out)
        assert m.dtype==bool

def test_tail_metrics_present(tmp_path):
    p=_panel();ep=tmp_path/"exec.csv.gz";p.to_csv(ep,index=False,compression="gzip")
    out,_=load_panel(TailStructureConfig(project_root=str(tmp_path),executable_panel_path=str(ep)))
    ev,y,mo=evaluate_states(out)
    assert "p05_improvement_vs_complement" in ev.columns
    assert "loss_1r_rate_reduction_vs_complement" in ev.columns
    assert "gain_loss_ratio_uplift_vs_complement" in ev.columns
    assert "nonoverlap_p05_r" in ev.columns
    assert not y.empty and not mo.empty

def test_readiness_uses_tail_gates():
    ev=pd.DataFrame([{
        "state":"X","n":2000,"symbols":300,
        "p05_improvement_vs_complement":.2,
        "loss_1r_rate_reduction_vs_complement":.02,
        "gain_loss_ratio":1.3,
        "gain_loss_ratio_uplift_vs_complement":.1,
        "right_left_tail_ratio_95_05":1.2,
        "nonoverlap_p05_r":-2.0,
        "nonoverlap_gain_loss_ratio":1.2,
        "top10_abs_contribution_fraction":.1,
    }])
    y=pd.DataFrame([{
        "state":"X","year":y,"p05_improvement_vs_complement":.1,
        "loss_1r_rate_reduction_vs_complement":.01
    } for y in range(2008,2018)])
    mo=pd.DataFrame([{
        "state":"X","month":f"2017-{m:02d}","loss_1r_rate_reduction_vs_complement":.01
    } for m in range(1,13)])
    r=build_readiness(ev,y,mo)
    assert bool(r.iloc[0]["development_ready_tail_state"])

def test_missing_condition_field_fails_closed(tmp_path):
    p=_panel();p.loc[0,"overall_score"]=np.nan
    ep=tmp_path/"exec.csv.gz";p.to_csv(ep,index=False,compression="gzip")
    with pytest.raises(TailStructureError,match="candidate-condition parity failed"):
        load_panel(TailStructureConfig(project_root=str(tmp_path),executable_panel_path=str(ep)))
