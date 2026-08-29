from pathlib import Path
import numpy as np
import pandas as pd

from trading_ai.research.m77.historical_price_integrity_lab import (
    IntegrityConfig, classify_daily_integrity, robust_tail_recalibration,
    contribution_concentration,
)


def _daily():
    dates=pd.bdate_range('2010-01-01',periods=90)
    close=np.linspace(10,12,90)
    close[70]=24.0
    return pd.DataFrame({'session_date':dates,'open':close,'high':close*1.01,'low':close*.99,'close':close,'volume':1e6,'vwap':close,'transactions':1000})


def test_daily_integrity_flags_large_discontinuity():
    cfg=IntegrityConfig(project_root='.')
    e=classify_daily_integrity('AAA',_daily(),cfg)
    assert not e.empty
    assert (e['classification']!='NORMAL').all()


def test_tail_recalibration_removes_extreme_return():
    pred=pd.DataFrame([
        {'symbol':'A','as_of':'2016-01-01','horizon':20,'test_year':2016,'probability_up':.99,'fwd_ret_20':10.0},
        {'symbol':'B','as_of':'2016-01-01','horizon':20,'test_year':2016,'probability_up':.98,'fwd_ret_20':.10},
        {'symbol':'C','as_of':'2016-01-01','horizon':20,'test_year':2016,'probability_up':.10,'fwd_ret_20':-.10},
        {'symbol':'D','as_of':'2016-01-01','horizon':20,'test_year':2016,'probability_up':.05,'fwd_ret_20':-.20},
    ])
    integ=pred[['symbol','as_of','horizon','test_year']].copy();integ['interval_integrity_clean']=[False,True,True,True];integ['source_return_matches_raw']=True
    cfg=IntegrityConfig(project_root='.',horizons=(20,),tail_fractions=(.5,),top_k=(1,))
    out,_=robust_tail_recalibration(pred,integ,cfg)
    raw=out[(out.direction=='LONG')&(out.treatment=='RAW')].iloc[0]
    clean=out[(out.direction=='LONG')&(out.treatment=='INTEGRITY_CLEAN')].iloc[0]
    assert raw.mean_return > 1
    assert np.isclose(clean.mean_return,.10)


def test_contribution_concentration_detects_single_symbol_dominance():
    pred=pd.DataFrame([
        {'symbol':'A','as_of':'2016-01-01','horizon':20,'test_year':2016,'probability_up':.99,'fwd_ret_20':5.0},
        {'symbol':'B','as_of':'2016-01-01','horizon':20,'test_year':2016,'probability_up':.98,'fwd_ret_20':.1},
        {'symbol':'C','as_of':'2016-01-01','horizon':20,'test_year':2016,'probability_up':.1,'fwd_ret_20':-.1},
        {'symbol':'D','as_of':'2016-01-01','horizon':20,'test_year':2016,'probability_up':.05,'fwd_ret_20':-.2},
    ])
    integ=pred[['symbol','as_of','horizon','test_year']].copy();integ['interval_integrity_clean']=True;integ['source_return_matches_raw']=True
    cfg=IntegrityConfig(project_root='.',horizons=(20,),tail_fractions=(.5,),top_k=(1,))
    out=contribution_concentration(pred,integ,cfg)
    r=out[(out.direction=='LONG')&(out.treatment=='RAW')].iloc[0]
    assert r.largest_symbol_contribution > .95


def test_development_only_mode_constant():
    cfg=IntegrityConfig(project_root='.')
    cfg.validate()
    assert cfg.execution_mode=='DEVELOPMENT_INTEGRITY_RECALIBRATION_ONLY'
