import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from trading_ai.research.m77.cross_sectional_relative_strength_persistence_leadership import (
    LeadershipConfig, LeadershipError, LEADERSHIP_STATES,
    _state_mask, build_readiness, evaluate_states, load_panel
)

def _panel():
    rows=[]
    for d in pd.bdate_range("2015-01-05",periods=40):
        for i in range(10):
            q=(i+1)/10
            rows.append({
                "symbol":f"S{i}","as_of":d,"entry_date":d+pd.offsets.BDay(1),
                "horizon":60,"target_atr":5.0,"stop_atr":3.0,
                "px_ret_20":q + (0.01 if d.day%2 else 0),
                "px_ret_60":q,
                "px_ret_126":q*0.9,
                "r_multiple":-0.2+0.6*q,
                "exit_day":30,
            })
    return pd.DataFrame(rows)

def test_same_date_cross_sectional_leadership_is_point_in_time(tmp_path):
    p=_panel()
    path=tmp_path/"panel.csv.gz"; p.to_csv(path,index=False,compression="gzip")
    out,meta=load_panel(LeadershipConfig(project_root=str(tmp_path),executable_panel_path=str(path)))
    assert out["as_of"].max()<=pd.Timestamp("2017-12-31")
    g=out[out["as_of"]==out["as_of"].min()].sort_values("px_ret_20")
    assert g.iloc[0]["rs20_rank"]==pytest.approx(.1)
    assert g.iloc[-1]["rs20_rank"]==pytest.approx(1.0)
    assert meta["consumed_2018_2026_rows_read"]==0

def test_post_2017_is_rejected(tmp_path):
    p=_panel()
    p.loc[0,"as_of"]="2018-01-02"
    path=tmp_path/"panel.csv.gz"; p.to_csv(path,index=False,compression="gzip")
    with pytest.raises(LeadershipError):
        load_panel(LeadershipConfig(project_root=str(tmp_path),executable_panel_path=str(path)))

def test_all_frozen_states_materialize():
    p=_panel()
    p["rs20_rank"]=p.groupby("as_of")["px_ret_20"].rank(pct=True)
    p["rs60_rank"]=p.groupby("as_of")["px_ret_60"].rank(pct=True)
    p["rs126_rank"]=p.groupby("as_of")["px_ret_126"].rank(pct=True)
    p["persist_20_60"]=(p.rs20_rank+p.rs60_rank)/2
    p["persist_20_60_126"]=(p.rs20_rank+p.rs60_rank+p.rs126_rank)/3
    p["stable_20_60_126"]=p[["rs20_rank","rs60_rank","rs126_rank"]].min(axis=1)
    p["accel_20_vs_60"]=p.rs20_rank-p.rs60_rank
    for state in LEADERSHIP_STATES:
        m=_state_mask(p,state)
        assert len(m)==len(p)
        assert m.dtype==bool

def test_evidence_contains_complement_and_nonoverlap():
    p=_panel()
    p["rs20_rank"]=p.groupby("as_of")["px_ret_20"].rank(pct=True)
    p["rs60_rank"]=p.groupby("as_of")["px_ret_60"].rank(pct=True)
    p["rs126_rank"]=p.groupby("as_of")["px_ret_126"].rank(pct=True)
    p["persist_20_60"]=(p.rs20_rank+p.rs60_rank)/2
    p["persist_20_60_126"]=(p.rs20_rank+p.rs60_rank+p.rs126_rank)/3
    p["stable_20_60_126"]=p[["rs20_rank","rs60_rank","rs126_rank"]].min(axis=1)
    p["accel_20_vs_60"]=p.rs20_rank-p.rs60_rank
    p["calendar_year"]=p["as_of"].dt.year
    p["calendar_month"]=p["as_of"].dt.to_period("M").astype(str)
    e,y,m=evaluate_states(p)
    assert len(e)==len(LEADERSHIP_STATES)
    assert "mean_r_uplift_vs_complement" in e.columns
    assert "nonoverlap_mean_r" in e.columns
    assert not y.empty and not m.empty

def test_readiness_is_explicit_and_not_auto_promotion():
    e=pd.DataFrame([{
        "state":"X","n":2000,"symbols":300,"mean_r":.3,"profit_factor":1.5,
        "equal_symbol_mean_r":.2,"top10_abs_contribution_fraction":.1,
        "mean_r_uplift_vs_complement":.1,"nonoverlap_mean_r":.2,
        "nonoverlap_profit_factor":1.4
    }])
    y=pd.DataFrame([{"state":"X","year":y,"mean_r":.3,"mean_r_uplift_vs_complement":.1} for y in range(2008,2018)])
    m=pd.DataFrame([{"state":"X","month":f"2017-{i:02d}","mean_r":.3,"mean_r_uplift_vs_complement":.1} for i in range(1,13)])
    r=build_readiness(e,y,m)
    assert bool(r.iloc[0]["development_ready_leadership_state"])


def test_missing_executable_features_join_from_frozen_m77_21_authority(tmp_path):
    p=_panel().drop(columns=["px_ret_20","px_ret_60","px_ret_126"])
    ep=tmp_path/"exec.csv.gz"
    p.to_csv(ep,index=False,compression="gzip")

    authority=_panel()[["symbol","as_of","px_ret_20","px_ret_60","px_ret_126"]].copy()
    authority=authority.drop_duplicates(["symbol","as_of"])
    ap=tmp_path/"panel.pkl.gz"
    authority.to_pickle(ap,compression="gzip",protocol=5)

    out,meta=load_panel(LeadershipConfig(
        project_root=str(tmp_path),
        executable_panel_path=str(ep),
        feature_authority_path=str(ap),
    ))
    assert meta["feature_authority_join_performed"] is True
    assert meta["feature_join_missing_rows"]==0
    assert out[["px_ret_20","px_ret_60","px_ret_126"]].notna().all().all()

def test_feature_authority_join_fails_closed_on_missing_identity(tmp_path):
    p=_panel().drop(columns=["px_ret_20","px_ret_60","px_ret_126"])
    ep=tmp_path/"exec.csv.gz"
    p.to_csv(ep,index=False,compression="gzip")

    authority=_panel()[["symbol","as_of","px_ret_20","px_ret_60","px_ret_126"]].copy()
    authority=authority.iloc[:-1].drop_duplicates(["symbol","as_of"])
    ap=tmp_path/"panel.pkl.gz"
    authority.to_pickle(ap,compression="gzip",protocol=5)

    with pytest.raises(LeadershipError,match="feature parity failed"):
        load_panel(LeadershipConfig(
            project_root=str(tmp_path),
            executable_panel_path=str(ep),
            feature_authority_path=str(ap),
        ))

def test_feature_authority_join_rejects_duplicate_keys(tmp_path):
    p=_panel().drop(columns=["px_ret_20","px_ret_60","px_ret_126"])
    ep=tmp_path/"exec.csv.gz"
    p.to_csv(ep,index=False,compression="gzip")

    authority=_panel()[["symbol","as_of","px_ret_20","px_ret_60","px_ret_126"]].copy()
    authority=pd.concat([authority,authority.iloc[[0]]],ignore_index=True)
    ap=tmp_path/"panel.pkl.gz"
    authority.to_pickle(ap,compression="gzip",protocol=5)

    with pytest.raises(LeadershipError,match="not unique"):
        load_panel(LeadershipConfig(
            project_root=str(tmp_path),
            executable_panel_path=str(ep),
            feature_authority_path=str(ap),
        ))
