from datetime import date
import sys, types
mod=types.ModuleType('trading_ai.database.session'); mod.SessionLocal=lambda: None
sys.modules.setdefault('trading_ai.database', types.ModuleType('trading_ai.database'))
sys.modules['trading_ai.database.session']=mod
from trading_ai.trend_intelligence.transition_repository import TrendTransitionRepository
class Scalar:
 def __init__(self,v): self.v=v
 def scalar_one_or_none(self): return self.v
class Session:
 def __init__(self,v): self.v=v
 def __enter__(self): return self
 def __exit__(self,*a): pass
 def execute(self,*a,**k): return Scalar(self.v)
def main():
 payload={'as_of_date':'2026-07-24','transition_state':'BULLISH_TRANSITION','transition_direction':'UP','breakout_state':'CONFIRMED_BREAKOUT','channel_position_pct':105,'momentum_acceleration_score':80,'volatility_state':'EXPANSION','volatility_percentile':88,'reversal_risk_score':20,'exhaustion_risk_score':15,'confirmation_score':90,'signal_adjustment':{'CALL':1.6,'PUT':-1.5}}
 r=TrendTransitionRepository(session_factory=lambda:Session(payload)); c=r.scanner_context('AAPL','CALL',reference_date=date(2026,7,24)); assert c['transition_context_status']=='FRESH'; assert c['transition_score_adjustment']==1.6
 print('All Trend Transition repository assertions passed.')
if __name__=='__main__':main()
