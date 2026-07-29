from __future__ import annotations
import json
from datetime import date,datetime
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

def _d(v): return v.date() if isinstance(v,datetime) else v if isinstance(v,date) else date.fromisoformat(str(v)[:10])
class TrendTransitionRepository:
    def __init__(self,session_factory=SessionLocal): self.session_factory=session_factory
    def latest(self,symbol):
        with self.session_factory() as s: v=s.execute(text('SELECT payload_json FROM stock_trend_transition_snapshot WHERE symbol=:s ORDER BY snapshot_timestamp DESC LIMIT 1'),{'s':symbol}).scalar_one_or_none()
        return v if isinstance(v,dict) else json.loads(v) if v else None
    def scanner_context(self,symbol,signal,maximum_age_days=3,reference_date=None):
        x=self.latest(symbol)
        neutral={'transition_context_status':'MISSING','transition_score_adjustment':0.0,'transition_state':'UNAVAILABLE','breakout_state':'UNAVAILABLE','reversal_risk_score':0.0,'exhaustion_risk_score':0.0,'transition_confirmation_score':50.0,'transition_context_warning':'No persisted transition snapshot.'}
        if not x:return neutral
        age=max(0,(_d(reference_date or date.today())-_d(x['as_of_date'])).days)
        if age>maximum_age_days: neutral.update(transition_context_status='STALE',transition_context_warning='Transition snapshot exceeds governed maximum age.',transition_snapshot_age_days=age); return neutral
        neutral.update(transition_context_status='FRESH',transition_snapshot_date=x['as_of_date'],transition_snapshot_age_days=age,transition_state=x['transition_state'],transition_direction=x['transition_direction'],breakout_state=x['breakout_state'],channel_position_pct=float(x['channel_position_pct']),momentum_acceleration_score=float(x['momentum_acceleration_score']),volatility_state=x['volatility_state'],volatility_percentile=float(x['volatility_percentile']),reversal_risk_score=float(x['reversal_risk_score']),exhaustion_risk_score=float(x['exhaustion_risk_score']),transition_confirmation_score=float(x['confirmation_score']),transition_score_adjustment=float(x.get('signal_adjustment',{}).get(str(signal).upper(),0.0)),transition_context_warning='')
        return neutral
