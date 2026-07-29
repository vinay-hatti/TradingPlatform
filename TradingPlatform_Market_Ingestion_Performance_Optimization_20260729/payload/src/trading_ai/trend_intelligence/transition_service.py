from __future__ import annotations
from datetime import datetime, timezone
import json
import pandas as pd
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from trading_ai.persistence_normalization import strict_json_dumps
from .transition_engine import TrendTransitionEngine

class TrendTransitionService:
    def __init__(self,session_factory=SessionLocal,engine=None): self.session_factory=session_factory; self.engine=engine or TrendTransitionEngine()
    def _symbols(self):
        with self.session_factory() as s: return list(s.execute(text('SELECT DISTINCT symbol FROM stock_trend_snapshot')).scalars())
    def _data(self,symbols):
        if not symbols:return {}
        with self.session_factory() as s:
            rows=[dict(r._mapping) for r in s.execute(text('SELECT symbol,date,close FROM price_history WHERE symbol = ANY(:symbols) ORDER BY symbol,date'),{'symbols':list(symbols)})]
        out={}
        for r in rows: out.setdefault(r['symbol'],[]).append(r)
        return {k:pd.DataFrame(v) for k,v in out.items()}
    def _phase1(self,symbol):
        with self.session_factory() as s:
            v=s.execute(text('SELECT payload_json FROM stock_trend_snapshot WHERE symbol=:s ORDER BY snapshot_timestamp DESC LIMIT 1'),{'s':symbol}).scalar_one_or_none()
        return v if isinstance(v,dict) else json.loads(v) if v else {}
    def build(self,symbols=None,persist=True,price_data=None):
        targets=list(symbols or self._symbols()); data=price_data if price_data is not None else self._data(targets); results=[]; skipped=[]; errors=[]
        for symbol in targets:
            try: results.append(self.engine.analyze(symbol,data.get(symbol,pd.DataFrame()),self._phase1(symbol)))
            except ValueError as exc:
                if 'insufficient transition history' in str(exc): skipped.append({'symbol':symbol,'reason':'INSUFFICIENT_TRANSITION_HISTORY','detail':str(exc)})
                else: errors.append({'symbol':symbol,'error':str(exc)})
            except Exception as exc: errors.append({'symbol':symbol,'error':str(exc)})
        if persist:self.persist(results)
        status='READY' if results and not errors else 'DEGRADED' if results else 'FAILED'
        return {'status':status,'snapshot_timestamp':datetime.now(timezone.utc).isoformat(),'requested_symbol_count':len(targets),'symbol_count':len(results),'skipped_count':len(skipped),'error_count':len(errors),'results':[x.to_dict() for x in results],'skipped':skipped,'errors':errors}
    def persist(self,snaps):
        with self.session_factory() as s:
            for x in snaps:
                p=x.to_dict(); s.execute(text('''INSERT INTO stock_trend_transition_snapshot(snapshot_timestamp,symbol,as_of_date,transition_state,transition_direction,breakout_state,confirmation_score,reversal_risk_score,exhaustion_risk_score,volatility_state,calculation_version,payload_json,created_at) VALUES(:ts,:sym,:d,:state,:dir,:bo,:conf,:rev,:exh,:vol,:v,:p,:ts) ON CONFLICT(snapshot_timestamp,symbol) DO UPDATE SET payload_json=EXCLUDED.payload_json,confirmation_score=EXCLUDED.confirmation_score'''),{'ts':x.snapshot_timestamp,'sym':x.symbol,'d':x.as_of_date,'state':x.transition_state,'dir':x.transition_direction,'bo':x.breakout_state,'conf':x.confirmation_score,'rev':x.reversal_risk_score,'exh':x.exhaustion_risk_score,'vol':x.volatility_state,'v':x.calculation_version,'p':strict_json_dumps(p)})
            s.commit()
