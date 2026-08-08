from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import os
from dotenv import dotenv_values

PROJECT_ROOT=Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE=PROJECT_ROOT/'.env'

@dataclass(frozen=True)
class ExecutionIntelligencePolicy:
    direct_polygon_enabled: bool=True
    max_quote_age_seconds: float=15.0
    max_price_drift_pct: float=3.0
    quote_stability_samples: int=3
    quote_stability_interval_ms: int=300
    minimum_execution_confidence: float=70.0
    minimum_edge_score: float=0.0
    minimum_expected_value: float=-1e18
    minimum_return_on_risk: float=-1e18
    maximum_spread_pct: float=100.0
    initial_limit_aggression_pct: float=35.0
    working_reprice_after_seconds: float=8.0
    working_reprice_min_change_pct: float=0.25
    maximum_reprices: int=4
    working_order_max_age_seconds: float=180.0
    policy_version: str='M70-EXECUTION-INTELLIGENCE-2.0'
    source: str=''
    def as_dict(self): return asdict(self)

def _bool(v,default=True):
    if v is None:return default
    return str(v).strip().lower() in {'1','true','yes','on','enabled'}

def load_execution_intelligence_policy(env_file:Path|str|None=None):
    path=Path(env_file) if env_file else DEFAULT_ENV_FILE
    vals=dict(dotenv_values(path)) if path.exists() else {}
    def get(name,default):
        value=vals.get(name)
        if value is None or str(value).strip()=='':value=os.getenv(name,default)
        return value
    p=ExecutionIntelligencePolicy(
      direct_polygon_enabled=_bool(get('TRADING_AI_EXECUTION_DIRECT_POLYGON_ENABLED','true')),
      max_quote_age_seconds=float(get('TRADING_AI_EXECUTION_MAX_QUOTE_AGE_SECONDS','15')),
      max_price_drift_pct=float(get('TRADING_AI_EXECUTION_MAX_PRICE_DRIFT_PCT','3')),
      quote_stability_samples=max(1,int(get('TRADING_AI_EXECUTION_QUOTE_STABILITY_SAMPLES','3'))),
      quote_stability_interval_ms=max(0,int(get('TRADING_AI_EXECUTION_QUOTE_STABILITY_INTERVAL_MS','300'))),
      minimum_execution_confidence=float(get('TRADING_AI_EXECUTION_MIN_CONFIDENCE','70')),
      minimum_edge_score=float(get('TRADING_AI_EXECUTION_MIN_EDGE_SCORE','0')),
      minimum_expected_value=float(get('TRADING_AI_EXECUTION_MIN_EXPECTED_VALUE','-1e18')),
      minimum_return_on_risk=float(get('TRADING_AI_EXECUTION_MIN_RETURN_ON_RISK','-1e18')),
      maximum_spread_pct=float(get('TRADING_AI_EXECUTION_MAX_SPREAD_PCT','100')),
      initial_limit_aggression_pct=float(get('TRADING_AI_EXECUTION_INITIAL_LIMIT_AGGRESSION_PCT','35')),
      working_reprice_after_seconds=float(get('TRADING_AI_EXECUTION_WORKING_REPRICE_AFTER_SECONDS','8')),
      working_reprice_min_change_pct=float(get('TRADING_AI_EXECUTION_WORKING_REPRICE_MIN_CHANGE_PCT','0.25')),
      maximum_reprices=max(0,int(get('TRADING_AI_EXECUTION_MAX_REPRICES','4'))),
      working_order_max_age_seconds=float(get('TRADING_AI_EXECUTION_WORKING_ORDER_MAX_AGE_SECONDS','180')),
      source=str(path) if path.exists() else 'process-environment/defaults')
    if p.max_quote_age_seconds<=0 or not 0<=p.max_price_drift_pct<=100 or not 0<=p.minimum_execution_confidence<=100:raise ValueError('Invalid M70 execution policy')
    if not 0<=p.initial_limit_aggression_pct<=100 or p.working_reprice_after_seconds<0 or p.working_reprice_min_change_pct<0 or p.working_order_max_age_seconds<=0:raise ValueError('Invalid M70 smart-order policy')
    return p
