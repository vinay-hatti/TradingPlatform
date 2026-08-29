from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trading_ai.research.m77.multivariate_tail_lab import (
    DEVELOPMENT_END,
    TailLabConfig,
    _embargo_days,
    _monotonicity,
    corrected_candidate_stationarity,
    walk_forward_tail_evidence,
)
from trading_ai.research.m77.edge_discovery_lab import EdgeLabError


def _panel() -> pd.DataFrame:
    rows=[]
    dates=pd.date_range('2003-01-03','2017-12-29',freq='W-FRI')
    for si,symbol in enumerate(['AAA','BBB','CCC','DDD']):
        base=50+si*10
        for i,d in enumerate(dates):
            ret=0.01 if (i+si)%3 else -0.005
            rows.append({
                'symbol':symbol,'as_of':d,'close':base+i*.05,
                'fwd_ret_15':ret,'fwd_ret_20':ret*1.1,'fwd_ret_30':ret*1.2,'fwd_ret_45':ret*1.3,'fwd_ret_60':ret*1.4,
                'fwd_ret_15_delay1':ret*.9,'mfe_15':abs(ret)*2,'mae_15':-abs(ret),
                'mfe_atr_15':2.0,'mae_atr_15':-1.0,
                'feature_x':float((i+si)%10),'feature_y':float(si),
            })
    return pd.DataFrame(rows)


def test_config_seals_post_2017():
    with pytest.raises(EdgeLabError):
        TailLabConfig(project_root='.', last_test_year=2018).validate()


def test_embargo_is_horizon_increasing():
    assert _embargo_days(60) > _embargo_days(30) > _embargo_days(15)


def test_tail_evidence_uses_year_local_tails():
    rows=[]
    for year in (2016,2017):
        for i in range(100):
            p=i/99
            rows.append({'symbol':f'S{i%20}','as_of':pd.Timestamp(f'{year}-06-30'),'horizon':30,'test_year':year,'probability_up':p,'fwd_ret_30':0.10 if i>=90 else -0.01})
    pred=pd.DataFrame(rows)
    cfg=TailLabConfig(project_root='.', horizons=(30,), tail_fractions=(.10,), top_k=(1,))
    tail,_,year=walk_forward_tail_evidence(pred,cfg)
    long=tail.iloc[0]
    assert long['direction']=='LONG'
    assert int(long['n'])==20
    assert float(long['win_rate'])==1.0
    assert set(year['test_year'])=={2016,2017}


def test_monotonicity_detects_improving_tail():
    tail=pd.DataFrame([
        {'horizon':30,'direction':'LONG','tail_fraction':.20,'win_rate':.60},
        {'horizon':30,'direction':'LONG','tail_fraction':.10,'win_rate':.65},
        {'horizon':30,'direction':'LONG','tail_fraction':.05,'win_rate':.70},
        {'horizon':30,'direction':'LONG','tail_fraction':.01,'win_rate':.80},
    ])
    out=_monotonicity(tail)
    assert out.iloc[0]['monotonic_fraction']==1.0


def test_corrected_stationarity_uses_full_development_eras(tmp_path: Path):
    panel=_panel()
    src=tmp_path/'lab';src.mkdir()
    pd.DataFrame([{
        'candidate_key':'abc','edge_id':'M77E-1','feature':'feature_x','operator':'RANGE','lower':-1.0,'upper':20.0,'value':np.nan,
        'direction':'LONG','horizon':15,'destruction_pass':True,
    }]).to_csv(src/'edge_registry.csv',index=False)
    out=corrected_candidate_stationarity(panel,src)
    assert set(out['era'])=={'2003_2007','2008_2012','2013_2017'}
    assert (out['n']>0).all()


def test_development_end_constant_is_sealed():
    assert DEVELOPMENT_END == pd.Timestamp('2017-12-31')
