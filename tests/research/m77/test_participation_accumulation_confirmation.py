import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.participation_accumulation_confirmation import (
    PARTICIPATION_STATES, ParticipationConfig, ParticipationError,
    _state_mask, _state_eligible_mask, build_readiness, evaluate_states, load_panel
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
    a["volume_ratio_10"]=.8+.05*i
    a["volume_ratio_20"]=.9+.04*i
    a["volume_ratio_60"]=1.0+.02*i
    a["volume_z_10"]=-.5+.15*i
    a["volume_z_20"]=-.4+.12*i
    a["volume_z_60"]=-.3+.10*i
    a["clv"]=-.8+.18*i
    a["body_range"]=.2+.03*i
    return a

def test_feature_authority_join_complete(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    p,m=load_panel(ParticipationConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    assert m["feature_join_missing_rows"]==0
    assert len(p)==len(e)

def test_post_2017_rejected(tmp_path):
    e=_exec_panel();e.loc[0,"as_of"]="2018-01-02";ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    with pytest.raises(ParticipationError):
        load_panel(ParticipationConfig(
            project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
        ))

def test_all_frozen_states_materialize(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    p,_=load_panel(ParticipationConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    for state in PARTICIPATION_STATES:
        m=_state_mask(p,state)
        assert len(m)==len(p)
        assert m.dtype==bool

def test_accumulation_and_distribution_are_distinct(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    p,_=load_panel(ParticipationConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    acc=_state_mask(p,"ACCUMULATION_CONFIRMATION")
    dist=_state_mask(p,"DISTRIBUTION_WARNING")
    assert not (acc & dist).any()

def test_evidence_has_complement_nonoverlap_and_time_stability(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority();ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    p,_=load_panel(ParticipationConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    ev,y,mo=evaluate_states(p)
    assert len(ev)==len(PARTICIPATION_STATES)
    assert "mean_r_uplift_vs_complement" in ev.columns
    assert "nonoverlap_mean_r" in ev.columns
    assert not y.empty and not mo.empty

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
    assert bool(r.iloc[0]["development_ready_participation_state"])

def test_missing_feature_parity_fails_closed(tmp_path):
    e=_exec_panel();ep=tmp_path/"exec.csv.gz";e.to_csv(ep,index=False,compression="gzip")
    a=_authority().iloc[:-1];ap=tmp_path/"panel.pkl.gz";a.to_pickle(ap,compression="gzip",protocol=5)
    with pytest.raises(ParticipationError,match="feature parity failed"):
        load_panel(ParticipationConfig(
            project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
        ))


def test_optional_diagnostics_do_not_invalidate_frozen_states(tmp_path):
    e=_exec_panel(); ep=tmp_path/"exec.csv.gz"; e.to_csv(ep,index=False,compression="gzip")
    a=_authority()
    # These fields are not used in any frozen M77.33 state and may legitimately be missing.
    a.loc[0,"volume_z_10"]=np.nan
    a.loc[1,"volume_z_20"]=np.nan
    a.loc[2,"volume_z_60"]=np.nan
    a.loc[3,"body_range"]=np.nan
    ap=tmp_path/"panel.pkl.gz"; a.to_pickle(ap,compression="gzip",protocol=5)
    p,m=load_panel(ParticipationConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    assert m["required_feature_join_missing_rows"]==0
    assert m["optional_diagnostic_missing_counts"]["volume_z_10"]==1
    assert m["optional_diagnostic_missing_counts"]["volume_z_20"]==1
    assert m["optional_diagnostic_missing_counts"]["volume_z_60"]==1
    assert m["optional_diagnostic_missing_counts"]["body_range"]==1
    assert len(p)==len(e)

def test_required_feature_missing_still_fails_closed(tmp_path):
    e=_exec_panel(); ep=tmp_path/"exec.csv.gz"; e.to_csv(ep,index=False,compression="gzip")
    a=_authority()
    a.loc[0,"volume_ratio_20"]=np.nan
    ap=tmp_path/"panel.pkl.gz"; a.to_pickle(ap,compression="gzip",protocol=5)
    with pytest.raises(ParticipationError,match="required point-in-time feature parity failed"):
        load_panel(ParticipationConfig(
            project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
        ))


def test_missing_clv_preserves_volume_only_population_and_excludes_only_clv_states(tmp_path):
    e=_exec_panel(); ep=tmp_path/"exec.csv.gz"; e.to_csv(ep,index=False,compression="gzip")
    a=_authority()
    a.loc[[0,1,2,3],"clv"]=np.nan
    ap=tmp_path/"panel.pkl.gz"; a.to_pickle(ap,compression="gzip",protocol=5)

    p,m=load_panel(ParticipationConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    assert m["required_feature_join_missing_rows"]==0
    assert m["clv_missing_rows"]==4
    assert len(p)==len(e)

    ev,_,_=evaluate_states(p)
    v=ev.set_index("state")
    for state in [
        "VOLUME_RATIO_20_TOP20",
        "VOLUME_RATIO_PERSISTENCE_TOP20",
        "VOLUME_ACCELERATION_TOP20",
        "VOLUME_DECELERATION_BOTTOM20",
    ]:
        assert v.loc[state,"eligible_n"]==len(e)
        assert v.loc[state,"excluded_missing_state_features_n"]==0

    for state in ["ACCUMULATION_CONFIRMATION","DISTRIBUTION_WARNING"]:
        assert v.loc[state,"eligible_n"]==len(e)-4
        assert v.loc[state,"excluded_missing_state_features_n"]==4

def test_missing_clv_is_neither_composite_state_nor_complement(tmp_path):
    e=_exec_panel(); ep=tmp_path/"exec.csv.gz"; e.to_csv(ep,index=False,compression="gzip")
    a=_authority()
    a.loc[0,"clv"]=np.nan
    key=(a.loc[0,"symbol"],pd.Timestamp(a.loc[0,"as_of"]))
    ap=tmp_path/"panel.pkl.gz"; a.to_pickle(ap,compression="gzip",protocol=5)

    p,_=load_panel(ParticipationConfig(
        project_root=str(tmp_path),executable_panel_path=str(ep),feature_authority_path=str(ap)
    ))
    row=p[(p["symbol"]==key[0])&(p["as_of"]==key[1])]
    assert len(row)==1
    idx=row.index[0]
    assert not bool(_state_eligible_mask(p,"ACCUMULATION_CONFIRMATION").loc[idx])
    assert not bool(_state_eligible_mask(p,"DISTRIBUTION_WARNING").loc[idx])
