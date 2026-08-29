from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.integrity_aware_bearish_recalibration import (
    IntegrityAwareBearishConfig,
    _annotate,
    _avoidance,
    _candidate_assessment,
    _concentration,
    _select_tail,
    _tail_recalibration,
    _treated_returns,
)


def _pred() -> pd.DataFrame:
    rows=[]
    for year in range(2008,2018):
        for wk in range(1,5):
            day=pd.Timestamp(year,1,1)+pd.Timedelta(days=7*wk)
            for i in range(100):
                p=i/100
                ret=-0.15 if i < 5 else (0.02 if i > 50 else -0.005)
                rows.append({"symbol":f"S{i:03d}","as_of":day,"horizon":20,"probability_up":p,"fwd_ret_20":ret,"test_year":year})
    return pd.DataFrame(rows)


def _integ(pred: pd.DataFrame) -> pd.DataFrame:
    d=pred[["symbol","as_of","horizon","test_year"]].copy()
    d["raw_authority_present"]=True; d["interval_integrity_event_count"]=0; d["interval_integrity_clean"]=True
    d["source_return_matches_raw"]=True; d["raw_recomputed_return"]=pred["fwd_ret_20"].values; d["integrity_clean_strict"]=True
    return d


def test_config_blocks_consumed_validation_and_final_holdout():
    IntegrityAwareBearishConfig(project_root="/tmp").validate()
    with pytest.raises(Exception):
        IntegrityAwareBearishConfig(project_root="/tmp", integrity_evidence="validation/integrity.csv.gz").validate()
    with pytest.raises(Exception):
        IntegrityAwareBearishConfig(project_root="/tmp", development_predictions="final_holdout/p.csv.gz").validate()


def test_tail_membership_is_formed_before_integrity_filter():
    p=_pred(); i=_integ(p)
    # Mark the exact bottom symbol dirty. Clean filtering must remove it, not replace it with S001.
    i.loc[i.symbol.eq("S000"),"integrity_clean_strict"]=False
    a=_annotate(p,i)
    s=_select_tail(a,20,0.01)
    assert set(s.symbol)=={"S000"}
    clean=_treated_returns(s,20,"INTEGRITY_CLEAN")
    assert clean.empty


def test_integrity_clean_recalibration_removes_dirty_extreme_without_changing_membership():
    p=_pred(); i=_integ(p)
    # Inject a dirty absurd return into a selected member.
    idx=p[(p.symbol=="S000")].index[0]; p.loc[idx,"fwd_ret_20"]=1000.0
    i.loc[(i.symbol=="S000") & (i.as_of==p.loc[idx,"as_of"]),"integrity_clean_strict"]=False
    a=_annotate(p,i)
    ev=_tail_recalibration(a)
    raw=ev[(ev.horizon==20)&(ev.tail_fraction==0.01)&(ev.treatment=="RAW")].iloc[0]
    clean=ev[(ev.horizon==20)&(ev.tail_fraction==0.01)&(ev.treatment=="INTEGRITY_CLEAN")].iloc[0]
    assert clean.n == raw.n - 1
    assert clean.mean_signed_return > raw.mean_signed_return


def test_avoidance_reports_severe_loss_capture_lift():
    a=_annotate(_pred(),_integ(_pred()))
    ev=_avoidance(a)
    r=ev[(ev.horizon==20)&(ev.tail_fraction_excluded==0.05)].iloc[0]
    assert r.severe_losses_captured_fraction > 0
    assert r.severe_loss_capture_lift_vs_random > 1
    assert r.severe_loss_rate_reduction > 0


def test_concentration_uses_absolute_signed_contribution():
    a=_annotate(_pred(),_integ(_pred()))
    ev=_concentration(a)
    r=ev[(ev.horizon==20)&(ev.tail_fraction==0.05)&(ev.treatment=="INTEGRITY_CLEAN")].iloc[0]
    assert 0 <= r.largest_symbol_abs_contribution_fraction <= 1
    assert r.top10_symbol_abs_contribution_fraction >= r.largest_symbol_abs_contribution_fraction


def test_candidate_assessment_requires_breadth_and_clean_barrier_expectancy():
    tails=pd.DataFrame([{"horizon":20,"tail_fraction":.01,"treatment":"INTEGRITY_CLEAN","n":2500,"unique_symbols":300,"short_win_rate":.60,"median_signed_return":.03,"mean_signed_return":.04,"positive_years":8,"years":10}])
    conc=pd.DataFrame([{"horizon":20,"tail_fraction":.01,"treatment":"INTEGRITY_CLEAN","top10_symbol_abs_contribution_fraction":.30}])
    barriers=pd.DataFrame([{"horizon":20,"tail_fraction":.01,"target_atr":3.,"stop_atr":1.,"expectancy_r":.15}])
    out=_candidate_assessment(tails,conc,barriers)
    assert bool(out.iloc[0].passes_development_integrity_protocol_readiness)

def test_end_to_end_runner_on_synthetic_development_data(tmp_path):
    from trading_ai.research.m77.integrity_aware_bearish_recalibration import run_lab
    root=tmp_path
    p=_pred(); i=_integ(p)
    pp=root/'research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz'; pp.parent.mkdir(parents=True)
    p.to_csv(pp,index=False,compression='gzip')
    ip=root/'research_data/m77_21_2_1/historical_price_integrity_lab/prediction_integrity_evidence.csv.gz'; ip.parent.mkdir(parents=True)
    # Persist only loader-authoritative fields; integrity_clean_strict is reconstructed by loader.
    i.drop(columns=['integrity_clean_strict']).to_csv(ip,index=False,compression='gzip')
    panel=p[['symbol','as_of']].drop_duplicates().copy()
    panel['short_barrier_t2p0_s1p5_h20']=np.where(panel['symbol'].isin(['S000','S001','S002','S003','S004']),1,-1)
    panel['short_days_t2p0_s1p5_h20']=5
    pn=root/'research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz'; pn.parent.mkdir(parents=True)
    panel.to_pickle(pn,compression='gzip')
    summary=run_lab(IntegrityAwareBearishConfig(project_root=str(root)))
    assert summary['status']=='COMPLETE'
    assert summary['validation_rows_read']==0
    assert summary['final_holdout_rows_read']==0
    out=root/'research_data/m77_22_1/integrity_aware_bearish_recalibration'
    assert (out/'integrity_aware_bearish_tail_recalibration.csv').exists()
    assert (out/'bottom1_protocol_readiness_assessment.csv').exists()
