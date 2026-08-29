from __future__ import annotations
from collections import defaultdict
from dataclasses import asdict
from datetime import date,datetime,timezone
from hashlib import sha256
import json
from typing import Any,Iterable
from uuid import uuid4
from sqlalchemy import text
from trading_ai.stock_intelligence.service import StockIntelligenceService
from trading_ai.stock_intelligence.publication_service import StockIntelligencePublicationService
VERSION="M77.1-UNDERLYING-REPLAY-1.0"
REPLAY_MODE="CURRENT_UNIVERSE_HISTORICAL_REPLAY"
CHAMPION_MODE="FROZEN_CURRENT_STOCK_INTELLIGENCE_UNDERLYING_ONLY"
def _json(v): return json.dumps(v,sort_keys=True,default=str,separators=(",",":"))
def _hash(v): return sha256(_json(v).encode()).hexdigest()
def _sign(d):
 d=str(d or '').upper(); return 1 if 'BULL' in d else -1 if 'BEAR' in d else 0
class HistoricalUnderlyingReplayService:
 """Isolated replay. Reads price_history; writes only historical_underlying_replay_* tables."""
 def __init__(self,session,intelligence_service=None): self.session=session; self.intelligence=intelligence_service or StockIntelligenceService()
 def _all_rows(self):
  g=defaultdict(list)
  for r in self.session.execute(text("SELECT symbol,date,open,high,low,close,volume FROM price_history ORDER BY symbol,date")).mappings():
   g[str(r['symbol']).upper()].append({'date':r['date'],'open':float(r['open']),'high':float(r['high']),'low':float(r['low']),'close':float(r['close']),'volume':float(r['volume'])})
  return g
 def _sessions(self): return set(self.session.scalars(text("SELECT date FROM price_history WHERE symbol='SPY' ORDER BY date")))
 @staticmethod
 def _continuity(rows):
  starts=[0]
  for i in range(1,len(rows)):
   p,c=rows[i-1],rows[i]; gap=(c['date']-p['date']).days; ratio=c['close']/p['close'] if p['close'] else 1
   if gap>45 or ratio>4 or ratio<.25: starts.append(i)
  i=starts[-1]; return rows[i]['date'],rows[i:],len(starts)-1
 def materialize_authority(self,minimum_warmup=300):
  grouped=self._all_rows(); sessions=self._sessions(); now=datetime.now(timezone.utc); counts=defaultdict(int)
  self.session.execute(text("DELETE FROM historical_underlying_replay_authority"))
  for symbol in sorted(grouped):
   original=grouped[symbol]; continuity_start,segment,breaks=self._continuity(original)
   valid=[r for r in segment if r['date'] in sessions and r['date'].weekday()<5]; invalid=len(segment)-len(valid)
   disposition='ELIGIBLE' if len(valid)>=minimum_warmup else 'EXCLUDED_INSUFFICIENT_WARMUP'; eligible=valid[minimum_warmup-1]['date'] if disposition=='ELIGIBLE' else None; counts[disposition]+=1
   evidence={'source':'price_history','session_authority':'SPY_DAILY_SESSIONS','source_first_date':original[0]['date'],'source_last_date':original[-1]['date'],'continuity_start':continuity_start,'identity_break_count':breaks,'valid_segment_rows':len(valid),'minimum_warmup':minimum_warmup,'excluded_invalid_session_rows':invalid,'survivorship_classification':REPLAY_MODE,'sector_history_policy':'NON_PIT_SECTOR_CONTEXT_DISABLED'}
   self.session.execute(text("""INSERT INTO historical_underlying_replay_authority(symbol,disposition,continuity_start,eligible_from,last_date,valid_observation_count,identity_break_count,invalid_session_count,authority_version,evidence_json,materialized_at) VALUES (:s,:d,:cs,:ef,:ld,:n,:b,:i,:v,CAST(:e AS jsonb),:m)"""),{'s':symbol,'d':disposition,'cs':continuity_start,'ef':eligible,'ld':valid[-1]['date'] if valid else original[-1]['date'],'n':len(valid),'b':breaks,'i':invalid,'v':VERSION,'e':_json(evidence),'m':now})
  self.session.commit(); return {'version':VERSION,'status':'READY','symbols':len(grouped),'dispositions':dict(counts)}
 def _authority(self,symbols=None):
  params={}; clause=''
  if symbols: params['symbols']=sorted({str(x).upper() for x in symbols}); clause=' WHERE symbol = ANY(:symbols)'
  return {str(r['symbol']):dict(r) for r in self.session.execute(text('SELECT * FROM historical_underlying_replay_authority'+clause),params).mappings()}
 @staticmethod
 def _engine_rows(rows): return [{**r,'date':r['date'].isoformat()} for r in rows]
 def _timeframes(self,rows):
  d=self._engine_rows(rows); return {'1d':d,'1w':StockIntelligencePublicationService._aggregate(d,'week'),'1mo':StockIntelligencePublicationService._aggregate(d,'month')}
 @staticmethod
 def _outcome(profile,future,as_of_close):
  sign=_sign(profile.direction); plan=profile.trade_plan; entry=getattr(plan,'entry',None); stop=getattr(plan,'stop',None); targets=getattr(plan,'targets',None)
  lo=getattr(entry,'zone_low',None) if entry else None; hi=getattr(entry,'zone_high',None) if entry else None; sp=getattr(stop,'recommended_stop',None) if stop else None
  prices=[float(t.price) for t in list(getattr(targets,'targets',[]) or []) if getattr(t,'price',None) is not None]
  triggered=False; entry_date=None; ep=None; stop_date=None; tdates={}; ambiguous=set(); mfe=0.; mae=0.
  for bar in future[:60]:
   if not triggered:
    if lo is None or hi is None: triggered=True; ep=as_of_close; entry_date=bar['date']
    elif float(bar['low'])<=float(hi) and float(bar['high'])>=float(lo): triggered=True; ep=min(max(as_of_close,float(lo)),float(hi)); entry_date=bar['date']
    else: continue
   e=float(ep or as_of_close); fav=((float(bar['high'])/e-1) if sign>=0 else (e/float(bar['low'])-1))*100; adv=((float(bar['low'])/e-1) if sign>=0 else (e/float(bar['high'])-1))*100; mfe=max(mfe,fav); mae=min(mae,adv)
   stop_hit=bool(sp is not None and ((float(bar['low'])<=sp) if sign>=0 else (float(bar['high'])>=sp)))
   hits=[]
   for idx,t in enumerate(prices,1):
    if idx not in tdates and ((float(bar['high'])>=t) if sign>=0 else (float(bar['low'])<=t)): hits.append(idx)
   if stop_hit and hits: ambiguous.update(hits)
   for idx in hits: tdates.setdefault(idx,bar['date'])
   if stop_hit and stop_date is None: stop_date=bar['date']
  fixed={}
  for h in (5,10,20,40,60):
   if len(future)>=h:
    raw=(float(future[h-1]['close'])/as_of_close-1)*100; fixed[str(h)]=round(raw*sign if sign else raw,6)
  tbs={}
  for idx in range(1,min(3,len(prices))+1):
   td=tdates.get(idx)
   if idx in ambiguous and td==stop_date: tbs[str(idx)]='AMBIGUOUS_SAME_BAR'
   elif td is None: tbs[str(idx)]=False
   else: tbs[str(idx)]=bool(stop_date is None or td<stop_date)
  return {'entry_triggered':triggered,'entry_date':entry_date,'entry_price':ep,'stop_date':stop_date,'target_dates':tdates,'target_before_stop':tbs,'ambiguous_same_bar':bool(ambiguous),'mfe_pct':round(mfe,6),'mae_pct':round(mae,6),'directional_returns_pct':fixed,'horizon_complete':len(future)>=60}
 def run_champion_baseline(self,start,end,cadence='WEEKLY',symbols=None,max_observations=None):
  cadence=cadence.upper()
  if cadence not in {'DAILY','WEEKLY','MONTHLY'}: raise ValueError('cadence must be DAILY, WEEKLY, or MONTHLY')
  authority=self._authority(symbols)
  if not authority: raise RuntimeError('Replay authority is empty; materialize authority first')
  run_id=f"m77-1-replay-{uuid4().hex}"; started=datetime.now(timezone.utc)
  self.session.execute(text("""INSERT INTO historical_underlying_replay_run(replay_run_id,replay_mode,champion_mode,start_date,end_date,cadence,status,authority_version,started_at,metadata_json) VALUES (:id,:mode,:champion,:start,:end,:cadence,'RUNNING',:version,:started,CAST(:meta AS jsonb))"""),{'id':run_id,'mode':REPLAY_MODE,'champion':CHAMPION_MODE,'start':start,'end':end,'cadence':cadence,'version':VERSION,'started':started,'meta':_json({'production_authority_effect':False,'external_context':'DISABLED_NON_PIT'})}); self.session.commit()
  sessions=self._sessions(); grouped=self._all_rows(); total=failures=ambiguous=0
  for symbol in sorted(authority):
   a=authority[symbol]
   if a['disposition']!='ELIGIBLE': continue
   rows=[r for r in grouped.get(symbol,[]) if r['date'] in sessions and r['date']>=a['continuity_start']]; index={r['date']:i for i,r in enumerate(rows)}
   dates=[d for d in index if start<=d<=end and d>=a['eligible_from']]
   if cadence=='WEEKLY':
    last={d.isocalendar()[:2]:d for d in dates}; dates=sorted(last.values())
   elif cadence=='MONTHLY':
    last={(d.year,d.month):d for d in dates}; dates=sorted(last.values())
   for as_of in dates:
    if max_observations is not None and total>=max_observations: break
    pos=index[as_of]; history=rows[max(0,pos-749):pos+1]; future=rows[pos+1:pos+61]
    try:
     profile=self.intelligence.analyze(symbol,self._timeframes(history),snapshot_timestamp=f'{as_of.isoformat()}T20:00:00+00:00',external_context={}); payload=asdict(profile); outcome=self._outcome(profile,future,float(rows[pos]['close'])); ambiguous+=int(outcome['ambiguous_same_bar']); pid=f'm77-1-pred-{uuid4().hex}'
     self.session.execute(text("""INSERT INTO historical_underlying_replay_prediction(prediction_id,replay_run_id,symbol,as_of,direction,primary_category,overall_score,confidence,state_hash,profile_json,lineage_json,created_at) VALUES (:pid,:rid,:s,:a,:d,:c,:o,:conf,:h,CAST(:p AS jsonb),CAST(:l AS jsonb),:now)"""),{'pid':pid,'rid':run_id,'s':symbol,'a':as_of,'d':profile.direction,'c':profile.scores.primary_category if profile.scores else None,'o':float(profile.scores.overall if profile.scores else 0),'conf':float(profile.confidence),'h':profile.state_hash,'p':_json(payload),'l':_json({'version':VERSION,'mode':REPLAY_MODE,'champion':CHAMPION_MODE,'as_of_cutoff':as_of,'production_authority_effect':False}),'now':datetime.now(timezone.utc)})
     self.session.execute(text("""INSERT INTO historical_underlying_replay_outcome(prediction_id,replay_run_id,symbol,as_of,status,entry_triggered,ambiguous_same_bar,mfe_pct,mae_pct,return_5d_pct,return_10d_pct,return_20d_pct,return_40d_pct,return_60d_pct,outcome_json,created_at) VALUES (:pid,:rid,:s,:a,:st,:et,:amb,:mfe,:mae,:r5,:r10,:r20,:r40,:r60,CAST(:oj AS jsonb),:now)"""),{'pid':pid,'rid':run_id,'s':symbol,'a':as_of,'st':'REALIZED' if outcome['horizon_complete'] else 'CENSORED','et':outcome['entry_triggered'],'amb':outcome['ambiguous_same_bar'],'mfe':outcome['mfe_pct'],'mae':outcome['mae_pct'],'r5':outcome['directional_returns_pct'].get('5'),'r10':outcome['directional_returns_pct'].get('10'),'r20':outcome['directional_returns_pct'].get('20'),'r40':outcome['directional_returns_pct'].get('40'),'r60':outcome['directional_returns_pct'].get('60'),'oj':_json(outcome),'now':datetime.now(timezone.utc)})
     total+=1
     if total%250==0: self.session.commit()
    except Exception as exc:
     failures+=1; self.session.execute(text("INSERT INTO historical_underlying_replay_failure(replay_run_id,symbol,as_of,error_type,error_message,created_at) VALUES (:r,:s,:a,:t,:m,:n)"),{'r':run_id,'s':symbol,'a':as_of,'t':type(exc).__name__,'m':str(exc)[:2000],'n':datetime.now(timezone.utc)}); self.session.commit()
   if max_observations is not None and total>=max_observations: break
  completed=datetime.now(timezone.utc); status='READY' if total and failures==0 else 'DEGRADED' if total else 'FAILED'; meta={'prediction_count':total,'failure_count':failures,'ambiguous_same_bar_count':ambiguous,'production_authority_effect':False}
  self.session.execute(text("UPDATE historical_underlying_replay_run SET status=:s,completed_at=:c,prediction_count=:p,failure_count=:f,metadata_json=CAST(:m AS jsonb) WHERE replay_run_id=:r"),{'s':status,'c':completed,'p':total,'f':failures,'m':_json(meta),'r':run_id}); self.session.commit(); return {'replay_run_id':run_id,'status':status,**meta}
