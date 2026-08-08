from __future__ import annotations
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy.orm import Session
from trading_ai.advanced_trade_builder.models import TradePlanModel
from .contracts import *
from .models import *
from .repository import PortfolioRepository
def now():return datetime.now(timezone.utc).isoformat()
def clamp(x,a=0,b=100):return max(a,min(b,float(x)))
class PortfolioIntelligenceService:
 def __init__(self,s:Session):self.s=s;self.repo=PortfolioRepository(s)
 @staticmethod
 def health(mark:PositionMark,source:dict|None=None)->PositionHealth:
  source=source or {};pnl=clamp(50+mark.unrealized_return_pct*2);expiry=100 if mark.days_to_expiry is None else clamp(mark.days_to_expiry*4);theta=clamp(70+mark.theta*10);risk=clamp(80-abs(mark.delta)*15);thesis=clamp(source.get('thesis_score',source.get('ai_score',75)))
  vals={'THESIS':thesis,'PNL':pnl,'EXPIRY':expiry,'THETA':theta,'RISK':risk};weights={'THESIS':.30,'PNL':.25,'EXPIRY':.20,'THETA':.10,'RISK':.15};score=sum(vals[k]*weights[k] for k in vals)
  alerts=[]
  if mark.days_to_expiry is not None and mark.days_to_expiry<=7:alerts.append('Expiration risk is elevated')
  if mark.unrealized_return_pct<=-20:alerts.append('Loss threshold requires review')
  if mark.theta<-1:alerts.append('Theta decay is accelerating')
  direction='IMPROVING' if score>=78 and mark.unrealized_pnl>=0 else 'DETERIORATING' if score<55 or len(alerts)>=2 else 'STABLE'
  drivers=tuple(HealthDriver(k,round(v,2),'UP' if v>=75 else 'DOWN' if v<55 else 'STABLE',round(weights[k]*v,2),f'{k.title()} component score') for k,v in vals.items())
  return PositionHealth(round(score,2),direction,round(sum(vals.values())/len(vals)/100,4),drivers,tuple(alerts))
 @staticmethod
 def decision(mark:PositionMark,health:PositionHealth)->PositionDecision:
  if health.score<40 or (mark.days_to_expiry is not None and mark.days_to_expiry<=3):return PositionDecision(PositionAction.CLOSE,.92,'CRITICAL','Thesis health or expiry risk requires exit','Stops further downside and assignment risk','REDUCES_RISK',('ROLL','SCALE_OUT'))
  if health.score<58:return PositionDecision(PositionAction.SCALE_OUT,.82,'HIGH','Position health is deteriorating','Reduces exposure while retaining optionality','REDUCES_RISK',('CLOSE','HEDGE'))
  if mark.days_to_expiry is not None and mark.days_to_expiry<=14:return PositionDecision(PositionAction.ROLL,.78,'HIGH','Expiration and decay risk are increasing','Extends duration and refreshes Greeks','MIXED',('SCALE_OUT','CLOSE'))
  if abs(mark.delta)>1.5:return PositionDecision(PositionAction.HEDGE,.74,'MEDIUM','Directional exposure exceeds preferred range','Reduces portfolio directional concentration','REDUCES_RISK',('SCALE_OUT','HOLD'))
  if health.score>=85 and mark.unrealized_return_pct>10:return PositionDecision(PositionAction.HOLD,.88,'LOW','Thesis remains strong and profitable','Preserves upside while health remains high','MAINTAINS_RISK',('SCALE_OUT',))
  return PositionDecision(PositionAction.HOLD,.72,'LOW','No governed adjustment trigger is active','Avoids unnecessary turnover','MAINTAINS_RISK',('SCALE_OUT','HEDGE'))
 def open_from_trade_plan(self,trade_plan_id,portfolio_id,mark_payload,actor,execution_id=None):
  tp=self.s.get(TradePlanModel,trade_plan_id)
  if not tp:raise KeyError('Trade plan not found')
  if tp.state not in ('PAPER_READY',):raise ValueError('Trade plan must be PAPER_READY')
  old=self.repo.by_trade_plan(portfolio_id,trade_plan_id)
  if old:return self.dto(old)
  mark=PositionMark(**mark_payload);health=self.health(mark,{'ai_score':tp.validation_json.get('ai_score',75)});decision=self.decision(mark,health);ts=now()
  m=ManagedPositionModel(position_id=f'POS-{uuid4().hex.upper()}',portfolio_id=portfolio_id,trade_plan_id=trade_plan_id,opportunity_id=tp.opportunity_id,intelligence_id=tp.intelligence_id,execution_id=execution_id,symbol=tp.symbol,strategy=tp.strategy,direction=tp.direction,state='OPEN',version=1,opened_at=ts,closed_at=None,entry_value=mark.market_value-mark.unrealized_pnl,realized_pnl=0,mark_json=mark.__dict__,health_json=health.to_dict(),decision_json=decision.to_dict(),metadata_json={'lineage_status':'VERIFIED','paper_only':True,'m62_lineage':dict(tp.execution_intent_json or {}).get('m62_lineage',{}),'decision_snapshot_id':dict(tp.execution_intent_json or {}).get('decision_snapshot_id'),'decision_state_hash':dict(tp.execution_intent_json or {}).get('decision_state_hash'),'dynamic_management':dict(tp.execution_intent_json or {}).get('dynamic_management',{}),'management_mode':'PLATFORM_MANAGED'},created_by=actor,created_at=ts,updated_at=ts)
  self.repo.add(m);self._health_snapshot(m,health);self._event(m,'POSITION_OPENED',actor,'Created from governed PAPER_READY trade plan',{'trade_plan_id':trade_plan_id});self.s.commit();return self.dto(m)
 def update_mark(self,id,expected_version,mark_payload,actor,reason):
  m=self.repo.get(id)
  if not m:raise KeyError('Position not found')
  if m.version!=expected_version:raise RuntimeError(f'Position version conflict: expected {expected_version}, actual {m.version}')
  if m.state in ('CLOSED','CANCELLED'):raise ValueError('Terminal position cannot be marked')
  mark=PositionMark(**mark_payload);health=self.health(mark,m.metadata_json);decision=self.decision(mark,health);m.version+=1;m.mark_json=mark.__dict__;m.health_json=health.to_dict();m.decision_json=decision.to_dict();m.updated_at=now();self._health_snapshot(m,health);self._event(m,'POSITION_MARKED',actor,reason,{'health':health.to_dict(),'decision':decision.to_dict()});self.s.commit();return self.dto(m)
 def action(self,id,expected_version,action,actor,reason,realized_pnl=0):
  m=self.repo.get(id)
  if not m:raise KeyError('Position not found')
  if m.version!=expected_version:raise RuntimeError(f'Position version conflict: expected {expected_version}, actual {m.version}')
  a=PositionAction(action);mapping={PositionAction.HOLD:m.state,PositionAction.SCALE_IN:'OPEN',PositionAction.SCALE_OUT:'PARTIAL',PositionAction.ROLL:'ROLLED',PositionAction.HEDGE:'HEDGED',PositionAction.CLOSE:'CLOSED'};m.version+=1;m.state=mapping[a];m.realized_pnl+=realized_pnl;m.updated_at=now();m.closed_at=m.updated_at if a==PositionAction.CLOSE else None;self._event(m,'POSITION_ACTION',actor,reason,{'action':a.value,'realized_pnl':realized_pnl});self.s.commit();return self.dto(m)
 def snapshot(self,portfolio_id,actor,cash=0,buying_power=0):
  items=self.repo.list(portfolio_id);active=[x for x in items if x.state not in ('CLOSED','CANCELLED')];mv=sum(x.mark_json.get('market_value',0) for x in active);upnl=sum(x.mark_json.get('unrealized_pnl',0) for x in active);rpnl=sum(x.realized_pnl for x in items);risk=sum(max(0,x.entry_value+x.mark_json.get('unrealized_pnl',0)*-1) for x in active);greeks={k:round(sum(x.mark_json.get(k,0) for x in active),6) for k in ('delta','gamma','theta','vega')};health=round(sum(x.health_json.get('score',0) for x in active)/len(active),2) if active else 100
  sector={};strategy={}
  for x in active:strategy[x.strategy]=strategy.get(x.strategy,0)+x.mark_json.get('market_value',0);sector[x.metadata_json.get('sector','UNCLASSIFIED')]=sector.get(x.metadata_json.get('sector','UNCLASSIFIED'),0)+x.mark_json.get('market_value',0)
  total=max(mv,1);conc={'largest_position_pct':round(max([x.mark_json.get('market_value',0) for x in active] or [0])/total*100,2),'active_positions':len(active)};p=PortfolioSnapshot(portfolio_id,now(),cash+mv,cash,buying_power,mv,upnl,rpnl,risk,health,len(active),greeks,sector,strategy,conc);model=PortfolioSnapshotModel(snapshot_id=f'PS-{uuid4().hex.upper()}',portfolio_id=portfolio_id,snapshot_timestamp=p.snapshot_timestamp,payload_json=p.to_dict(),generated_by=actor);self.repo.add(model);self.s.commit();return {'snapshot_id':model.snapshot_id,**p.to_dict()}
 def attribution(self,id,actor):
  m=self.repo.get(id)
  if not m:raise KeyError('Position not found')
  mark=m.mark_json;ret=mark.get('unrealized_return_pct',0) if m.state!='CLOSED' else (m.realized_pnl/max(m.entry_value,1)*100);payload={'position_id':id,'symbol':m.symbol,'outcome_return_pct':round(ret,4),'opportunity_quality':round(m.health_json.get('drivers',[{'score':75}])[0].get('score',75),2),'construction_quality':85 if m.metadata_json.get('lineage_status')=='VERIFIED' else 60,'risk_management_quality':90 if m.state in ('PARTIAL','CLOSED','HEDGED','ROLLED') else 75,'execution_quality':80 if m.execution_id else 65,'decision_alignment':m.decision_json.get('action'),'result':'WIN' if ret>0 else 'LOSS' if ret<0 else 'FLAT'};a=PositionAttributionModel(attribution_id=f'ATTR-{uuid4().hex.upper()}',position_id=id,generated_at=now(),payload_json=payload,generated_by=actor);self.repo.add(a);self._event(m,'ATTRIBUTION_GENERATED',actor,'Generated governed position attribution',payload);self.s.commit();return {'attribution_id':a.attribution_id,'generated_at':a.generated_at,**payload}
 def _health_snapshot(self,m,h):self.repo.add(PositionHealthSnapshotModel(health_snapshot_id=f'HS-{uuid4().hex.upper()}',position_id=m.position_id,position_version=m.version,snapshot_timestamp=now(),health_score=h.score,direction=h.direction,confidence=h.confidence,payload_json=h.to_dict()))
 def _event(self,m,event,actor,reason,payload):self.repo.add(PositionEventModel(event_id=f'PE-{uuid4().hex.upper()}',position_id=m.position_id,position_version=m.version,event_type=event,actor=actor,reason=reason,event_timestamp=now(),payload_json=payload))
 @staticmethod
 def dto(m):
  return {'position_id':m.position_id,'portfolio_id':m.portfolio_id,'trade_plan_id':m.trade_plan_id,'opportunity_id':m.opportunity_id,'intelligence_id':m.intelligence_id,'execution_id':m.execution_id,'symbol':m.symbol,'strategy':m.strategy,'direction':m.direction,'state':m.state,'version':m.version,'opened_at':m.opened_at,'closed_at':m.closed_at,'entry_value':m.entry_value,'realized_pnl':m.realized_pnl,'mark':m.mark_json,'health':m.health_json,'decision':m.decision_json,'metadata':m.metadata_json}
