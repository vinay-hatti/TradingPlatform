from __future__ import annotations
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy.orm import Session
from trading_ai.opportunity_domain.models import OpportunityModel
from trading_ai.institutional_intelligence.repository import IntelligenceRepository
from .contracts import BuildTradePlanRequest,TradePlan,TradePlanState,TradeLeg
from .models import TradePlanModel,TradePlanAuditModel
from .repository import TradePlanRepository

def now():return datetime.now(timezone.utc).isoformat()
class AdvancedTradeBuilderService:
 def __init__(self,session:Session):self.session=session;self.repo=TradePlanRepository(session)
 @staticmethod
 def economics(legs:tuple[TradeLeg,...],capital:float,risk_pct:float):
  debit=sum(l.limit_price*l.quantity*100 for l in legs if l.side.value=='BUY')
  credit=sum(l.limit_price*l.quantity*100 for l in legs if l.side.value=='SELL')
  net=max(0.0,debit-credit); budget=capital*risk_pct/100
  # Defined-risk spreads: debit is max loss; credit structures require width-based collateral.
  if net>0:max_loss=net
  else:
   strikes=sorted({l.strike for l in legs});width=(max(strikes)-min(strikes))*100 if len(strikes)>1 else budget
   max_loss=max(0.0,width+debit-credit)
  net_g={k:round(sum((getattr(l,k) or 0)*l.quantity*(1 if l.side.value=='BUY' else -1) for l in legs),6) for k in ('delta','gamma','theta','vega')}
  max_profit=None
  if len(legs)==2 and len({l.option_right for l in legs})==1:
   width=abs(legs[0].strike-legs[1].strike)*100*min(l.quantity for l in legs)
   max_profit=max(0.0,width-max_loss) if net>0 else max(0.0,credit-debit)
  rr=round(max_profit/max_loss,4) if max_profit is not None and max_loss>0 else None
  checks={'has_legs':bool(legs),'max_four_legs':len(legs)<=4,'positive_quantities':all(l.quantity>0 for l in legs),'single_expiry':len({l.expiry for l in legs})==1,'risk_within_budget':max_loss<=budget+1e-9,'defined_risk':len(legs)<=2 or net>0}
  checks['valid']=all(checks.values())
  return debit,credit,max_loss,max_profit,rr,budget,net_g,checks
 def build(self,r:BuildTradePlanRequest)->TradePlan:
  opp=self.session.get(OpportunityModel,r.opportunity_id)
  if not opp:raise KeyError('Opportunity not found')
  if opp.version!=r.expected_opportunity_version:raise RuntimeError(f'Opportunity version conflict: expected {r.expected_opportunity_version}, actual {opp.version}')
  existing=self.repo.find_source(r.opportunity_id,opp.version,r.account_id,r.strategy)
  if existing:return self._dto(existing)
  debit,credit,max_loss,max_profit,rr,budget,greeks,checks=self.economics(r.legs,r.capital,r.risk_budget_pct)
  latest=IntelligenceRepository(self.session).latest(r.opportunity_id); ts=now()
  state=TradePlanState.VALIDATED if checks['valid'] else TradePlanState.DRAFT
  m=TradePlanModel(trade_plan_id=f'TP-{uuid4().hex.upper()}',opportunity_id=opp.opportunity_id,opportunity_version=opp.version,intelligence_id=latest.intelligence_id if latest else None,account_id=r.account_id,symbol=opp.symbol,direction=opp.direction,strategy=r.strategy,state=state.value,version=1,capital=r.capital,risk_budget_pct=r.risk_budget_pct,risk_budget_amount=budget,estimated_debit=debit,estimated_credit=credit,max_loss=max_loss,max_profit=max_profit,reward_risk_ratio=rr,net_greeks_json=greeks,validation_json=checks,legs_json=[{'side':l.side.value,'quantity':l.quantity,'option_right':l.option_right.value,'strike':l.strike,'expiry':l.expiry,'limit_price':l.limit_price,'delta':l.delta,'gamma':l.gamma,'theta':l.theta,'vega':l.vega,'option_symbol':l.option_symbol} for l in r.legs],execution_intent_json={},notes=r.notes,created_by=r.actor,created_at=ts,updated_at=ts)
  self.repo.add(m);self._audit(m,'TRADE_PLAN_CREATED',r.actor,'Built from canonical opportunity and intelligence',{'validation':checks});self.session.commit();return self._dto(m)
 def transition(self,id,expected_version,target,actor,reason):
  m=self.repo.get(id)
  if not m:raise KeyError('Trade plan not found')
  if m.version!=expected_version:raise RuntimeError(f'Trade plan version conflict: expected {expected_version}, actual {m.version}')
  allowed={'DRAFT':['VALIDATED','CANCELLED'],'VALIDATED':['APPROVED','CANCELLED'],'APPROVED':['PAPER_READY','CANCELLED'],'PAPER_READY':['CANCELLED'],'CANCELLED':[]}
  if target not in allowed[m.state]:raise ValueError(f'Invalid transition {m.state} -> {target}')
  if target in ('APPROVED','PAPER_READY') and not m.validation_json.get('valid'):raise ValueError('Invalid trade plan cannot be approved')
  m.version+=1;m.state=target;m.updated_at=now()
  if target=='PAPER_READY':m.execution_intent_json={'environment':'PAPER','account_id':m.account_id,'symbol':m.symbol,'strategy':m.strategy,'legs':m.legs_json,'max_loss':m.max_loss,'live_trading_enabled':False,'submission_status':'READY_FOR_EXISTING_ROUTER'}
  self._audit(m,'TRADE_PLAN_TRANSITIONED',actor,reason,{'state':target,'execution_intent':m.execution_intent_json});self.session.commit();return self._dto(m)
 def _audit(self,m,event,actor,reason,payload):self.repo.add(TradePlanAuditModel(audit_id=f'TPA-{uuid4().hex.upper()}',trade_plan_id=m.trade_plan_id,trade_plan_version=m.version,event_type=event,actor=actor,reason=reason,event_timestamp=now(),payload_json=payload))
 @staticmethod
 def _dto(m):
  legs=tuple(TradeLeg(**{**x,'side':__import__('trading_ai.advanced_trade_builder.contracts',fromlist=['LegSide']).LegSide(x['side']),'option_right':__import__('trading_ai.advanced_trade_builder.contracts',fromlist=['OptionRight']).OptionRight(x['option_right'])}) for x in m.legs_json)
  return TradePlan(m.trade_plan_id,m.opportunity_id,m.opportunity_version,m.intelligence_id,m.account_id,m.symbol,m.direction,m.strategy,TradePlanState(m.state),m.version,m.capital,m.risk_budget_pct,m.risk_budget_amount,m.estimated_debit,m.estimated_credit,m.max_loss,m.max_profit,m.reward_risk_ratio,dict(m.net_greeks_json),dict(m.validation_json),legs,m.created_by,m.created_at,m.updated_at,m.notes)
