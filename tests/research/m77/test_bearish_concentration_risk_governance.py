from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
from trading_ai.research.m77.bearish_concentration_risk_governance import (
    BearishConcentrationConfig,_annotate,_exclusion_stress,_nonoverlap_symbol_filter,_readiness,_severe_loss_capture,_select_bottom_tail,_stats
)

def pred():
    rows=[]
    for year in range(2008,2018):
        for wk in range(1,9):
            day=pd.Timestamp(year,1,1)+pd.Timedelta(days=7*wk)
            for i in range(500):
                ret=-0.20 if i<2 else (-0.04 if i<8 else 0.01)
                rows.append({'symbol':f'S{i:03d}','as_of':day,'horizon':20,'probability_up':i/500,'fwd_ret_20':ret,'test_year':year})
    return pd.DataFrame(rows)

def integ(p):
    d=p[['symbol','as_of','horizon']].copy(); d['integrity_clean_strict']=True; return d

def test_config_blocks_validation_final_holdout():
    BearishConcentrationConfig(project_root='/tmp').validate()
    with pytest.raises(Exception): BearishConcentrationConfig(project_root='/tmp',development_predictions='validation/x.csv.gz').validate()

def test_bottom_tail_is_contemporaneous():
    p=pred(); s=_select_bottom_tail(p,20,.01)
    assert set(s.symbol)=={'S000','S001','S002','S003','S004'}
    assert s.as_of.nunique()==80

def test_exclusion_stress_removes_contributors_without_reranking():
    a=_annotate(pred(),integ(pred())); ev=_exclusion_stress(a)
    base=ev[(ev.horizon==20)&(ev.removed_top_contributor_symbols==0)].iloc[0]
    cut=ev[(ev.horizon==20)&(ev.removed_top_contributor_symbols==1)].iloc[0]
    assert cut.n < base.n
    assert cut.unique_symbols < base.unique_symbols

def test_nonoverlap_reduces_repeated_symbol_exposure():
    a=_annotate(pred(),integ(pred())); d=_select_bottom_tail(a,20,.01); d['raw_return']=d.fwd_ret_20; d['signed_return']=-d.raw_return; d['short_win']=d.raw_return<0
    x=_nonoverlap_symbol_filter(d,20)
    assert len(x)<len(d)

def test_severe_loss_capture_lift_exceeds_random_on_fixture():
    a=_annotate(pred(),integ(pred())); ev=_severe_loss_capture(a)
    r=ev[(ev.horizon==20)&(ev.loss_threshold==-0.10)].iloc[0]
    assert r.capture_lift_vs_random>1

def test_readiness_requires_deconcentration_and_capture():
    ex=pd.DataFrame([{'horizon':20,'removed_top_contributor_symbols':10,'short_win_rate':.58,'equal_symbol_mean_signed_return':.02,'equal_symbol_positive_fraction':.60}])
    rp=pd.DataFrame([{'horizon':20,'mode':'NONOVERLAPPING_PER_SYMBOL','short_win_rate':.56,'mean_signed_return':.01}])
    cp=pd.DataFrame([{'horizon':20,'loss_threshold':-.10,'capture_lift_vs_random':3.0}])
    out=_readiness(ex,rp,cp)
    assert bool(out.iloc[0].passes_deconcentrated_risk_governance_readiness)

def test_candidate_long_veto_improves_candidate_losses_when_flag_available():
    from trading_ai.research.m77.bearish_concentration_risk_governance import _candidate_long_veto
    p=pred(); a=_annotate(p,integ(p))
    panel=p[['symbol','as_of']].drop_duplicates().copy()
    panel['eligible_candidate']=panel['symbol'].isin([f'S{i:03d}' for i in range(250)])
    ev,audit=_candidate_long_veto(a,panel)
    r=ev[(ev.candidate_flag_column=='eligible_candidate')&(ev.horizon==20)].iloc[0]
    assert r.vetoed_n>0
    assert r.loss_rate_improvement>0
    assert not audit.empty


def test_end_to_end_runner_on_synthetic_development_data(tmp_path):
    from trading_ai.research.m77.bearish_concentration_risk_governance import run_lab
    p=pred()
    pp=tmp_path/'research_data/m77_21_2/multivariate_predictive_tail_lab/walk_forward_predictions.csv.gz'; pp.parent.mkdir(parents=True)
    p.to_csv(pp,index=False,compression='gzip')
    i=p[['symbol','as_of','horizon']].copy(); i['raw_authority_present']=True; i['interval_integrity_clean']=True; i['source_return_matches_raw']=True; i['interval_integrity_event_count']=0
    ip=tmp_path/'research_data/m77_21_2_1/historical_price_integrity_lab/prediction_integrity_evidence.csv.gz'; ip.parent.mkdir(parents=True)
    i.to_csv(ip,index=False,compression='gzip')
    panel=p[['symbol','as_of']].drop_duplicates().copy(); panel['eligible_candidate']=panel.symbol.isin([f'S{i:03d}' for i in range(250)])
    pn=tmp_path/'research_data/m77_21_0/edge_discovery_lab/checkpoints/panel.pkl.gz'; pn.parent.mkdir(parents=True)
    panel.to_pickle(pn,compression='gzip')
    summary=run_lab(BearishConcentrationConfig(project_root=str(tmp_path)))
    assert summary['status']=='COMPLETE'
    assert summary['validation_rows_read']==0 and summary['final_holdout_rows_read']==0
    out=tmp_path/'research_data/m77_22_2/bearish_concentration_risk_governance'
    assert (out/'bearish_top_contributor_exclusion_stress.csv').exists()
    assert (out/'candidate_long_bearish_veto_evidence.csv').exists()

def test_report_rendering_has_no_tabulate_dependency(tmp_path):
    import inspect
    import trading_ai.research.m77.bearish_concentration_risk_governance as mod
    source = inspect.getsource(mod)
    assert '.to_markdown(' not in source
    frame = pd.DataFrame([{'horizon':20,'passes':True,'metric':0.123456789}])
    rendered = mod._markdown_table(frame)
    assert '| horizon | passes | metric |' in rendered
    assert '0.123457' in rendered
