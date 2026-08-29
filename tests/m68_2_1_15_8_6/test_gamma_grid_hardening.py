from __future__ import annotations
from datetime import date
from pathlib import Path

from trading_ai.institutional_market_structure.engine import (
    InstitutionalMarketStructureEngine,
    _M,
    _clip,
    _greeks,
)

ROOT = Path(__file__).resolve().parents[2]


def _metrics(count: int = 96):
    rows=[]
    for j in range(count):
        dte=7+(j%120)
        strike=float(60+(j%81))
        right='CALL' if j%2==0 else 'PUT'
        iv=.15+(j%25)*.01
        sign=1.0 if right=='CALL' else -1.0
        rows.append(_M(date(2026,12,18),dte,strike,right,100+j,50+j,iv,1.0,1.2,1.1,.5,.01,0.0,0.0,sign,0.0,0.0,0.0,0.0,0.0,.1,True))
    return rows


def _reference(engine, metrics, spot):
    pts=[]
    for i in range(engine.policy.gamma_grid_steps):
        s=spot*(engine.policy.gamma_grid_min_factor+(engine.policy.gamma_grid_max_factor-engine.policy.gamma_grid_min_factor)*i/(engine.policy.gamma_grid_steps-1))
        total=0.0
        for m in metrics:
            _,g,_,_=_greeks(s,m.strike,max(m.dte/365,1/365),m.iv,engine.policy.risk_free_rate,m.right)
            total+=m.sign*g*m.oi*engine.policy.contract_multiplier*s*s*.01
        pts.append((s,total))
    for (s1,g1),(s2,g2) in zip(pts,pts[1:]):
        if g1==0:
            return s1,s1,s1,1.0
        if g1*g2<0:
            flip=s1+(s2-s1)*abs(g1)/(abs(g1)+abs(g2)); spacing=(s2-s1)/spot
            return flip,s1,s2,_clip(1-spacing*10,0,1)
    return None,None,None,0.0


def test_gamma_grid_is_numerically_identical_to_governed_reference():
    engine=InstitutionalMarketStructureEngine()
    metrics=_metrics()
    expected=_reference(engine,metrics,100.0)
    actual=engine._gamma_flip_grid(metrics,100.0)
    assert actual == expected


def test_gamma_grid_removes_unused_full_greeks_from_shock_loop():
    source=(ROOT/'src/trading_ai/institutional_market_structure/engine.py').read_text()
    block=source[source.index('def _gamma_flip_grid'):source.index('@staticmethod\n    def _slope')]
    assert '_greeks(' not in block
    assert 'gamma=_pdf(d1)/(s*iv*rt)' in block
    assert 'prepared=[' in block
    assert 'for strike,t,iv,sign,oi in prepared:' in block
    assert 'gamma_grid_steps' in block
    assert 'gamma_grid_min_factor' in block
    assert 'gamma_grid_max_factor' in block


def test_no_dealer_formula_or_grid_resolution_change():
    source=(ROOT/'src/trading_ai/institutional_market_structure/engine.py').read_text()
    assert "ESTIMATOR_VERSION='44.2.1'" in source
    assert 'self.policy.gamma_grid_steps' in source
    assert 'self.policy.gamma_grid_min_factor' in source
    assert 'self.policy.gamma_grid_max_factor' in source
    assert 'total+=sign*gamma*oi*multiplier*s*s*.01' in source
