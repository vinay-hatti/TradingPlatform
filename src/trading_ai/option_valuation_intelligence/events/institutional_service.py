from __future__ import annotations
import json
from datetime import date,datetime,timedelta,timezone
from sqlalchemy import text
from .analytics import weighted_expected_move,confidence_score,classify_event_edge
from .forecast_resolver import GovernedForecastResolver
from .implied_move import GovernedImpliedMoveResolver
from .historical_repository import HistoricalEventOutcomeRepository
class InstitutionalEventIntelligenceService:
 def __init__(self,session_factory):self.session_factory=session_factory
 def _historical(self,s,e):
  sym='SPY' if str(e['symbol']).upper() in ('*','ALL') else str(e['symbol']).upper()
  return HistoricalEventOutcomeRepository().distribution_for(s,symbol=sym,event_type=e['event_type'])
 def _implied(self,s,e):
  ed=date.fromisoformat(str(e['event_date'])[:10])
  return GovernedImpliedMoveResolver().resolve(s,symbol=str(e['symbol']),event_date=ed)
 def _forecast(self,s,e):
  ed=date.fromisoformat(str(e['event_date'])[:10])
  return GovernedForecastResolver().resolve(s,symbol=str(e['symbol']),event_date=ed)
 def build(self,limit=None):
  now=datetime.now(timezone.utc).isoformat();updated=unchanged=missing=0;classes={}
  with self.session_factory() as s:
   # Finalize elapsed ACTIVE events before current-event valuation.
   s.execute(text("UPDATE institutional_option_valuation_events SET status='COMPLETED' WHERE status='ACTIVE' AND event_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' AND SUBSTRING(event_date FROM 1 FOR 10)::date < CURRENT_DATE"))
   date_expr = "CASE WHEN event_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' THEN SUBSTRING(event_date FROM 1 FOR 10)::date ELSE NULL END"
   sql = (
    "SELECT * FROM institutional_option_valuation_events "
    "WHERE status='ACTIVE' "
    f"AND ({date_expr}) >= CURRENT_DATE "
    f"ORDER BY ({date_expr}), event_id"
    + (" LIMIT :n" if limit else "")
   )
   rows=s.execute(text(sql),{'n':limit} if limit else {}).mappings().all()
   for e in rows:
    h,n,hd=self._historical(s,e);i,snap,liq,ide=self._implied(s,e);f,fd=self._forecast(s,e);x,w=weighted_expected_move(i,h,f);vals=[v for v in (i,h,f) if v];agree=0 if len(vals)<2 else max(0,100-(max(vals)-min(vals))/max(vals)*100);conf=confidence_score(date_confirmed=e.get('date_status')!='TENTATIVE',time_confirmed=e.get('event_time_status') in ('CONFIRMED','CONFIRMED_SESSION'),implied=bool(i),historical_samples=n,forecast=bool(f),liquidity_score=liq,agreement_score=agree,source_fresh=True);cl=classify_event_edge(i,x,conf);classes[cl]=classes.get(cl,0)+1;ev=dict(e.get('evidence_json') or {});ev['institutional_event_intelligence']={'historical':hd,'implied':ide,'forecast':fd,'weights':w,'agreement_score':agree,'liquidity_score':liq,'classification':cl,'calculated_at':now}
    if e.get('implied_move_pct')==i and e.get('historical_move_pct')==h and e.get('forecast_move_pct')==f and e.get('expected_move_pct')==x and e.get('confidence')==conf:unchanged+=1;continue
    s.execute(text("UPDATE institutional_option_valuation_events SET implied_move_pct=:i,historical_move_pct=:h,forecast_move_pct=:f,expected_move_pct=:x,historical_sample_size=:n,confidence=:c,calculation_method='INSTITUTIONAL_EVENT_INTELLIGENCE_V4',options_snapshot_id=:snap,evidence_json=CAST(:ev AS jsonb) WHERE event_id=:id"),{'i':i,'h':h,'f':f,'x':x,'n':n,'c':conf,'snap':snap,'ev':json.dumps(ev,default=str),'id':e['event_id']});updated+=1;missing+=int(x is None)
    s.execute(text("INSERT INTO institutional_event_pricing_snapshots(snapshot_id,event_id,snapshot_timestamp,implied_move_pct,historical_move_pct,forecast_move_pct,expected_move_pct,confidence,classification,payload_json) VALUES(:sid,:eid,:ts,:i,:h,:f,:x,:c,:cl,CAST(:p AS jsonb)) ON CONFLICT(snapshot_id) DO UPDATE SET payload_json=EXCLUDED.payload_json,confidence=EXCLUDED.confidence"),{'sid':f"m696-{e['event_id']}-{date.today()}",'eid':e['event_id'],'ts':now,'i':i,'h':h,'f':f,'x':x,'c':conf,'cl':cl,'p':json.dumps(ev,default=str)})
   s.commit()
  return {'status':'READY' if missing==0 else 'DEGRADED','events':len(rows),'updated':updated,'unchanged':unchanged,'missing_components':missing,'classifications':classes,'completed_at':now}
