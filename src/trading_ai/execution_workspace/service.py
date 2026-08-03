from __future__ import annotations
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import select,text
from sqlalchemy.orm import Session
from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.authoritative_paper_trading.database_models import CanonicalOrderModel
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel,BrokerAccountSnapshotModel,BrokerOrderModel
from trading_ai.broker.ibkr.order_models import IbkrPaperComboLegRequest,IbkrPaperComboOrderRequest,IbkrPaperOrderRequest
from trading_ai.broker.ibkr.models import IbkrPaperConnectionConfig
from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport
from trading_ai.broker.ibkr.order_service import IbkrPaperOrderGovernanceService,IbkrPaperOrderService
from trading_ai.portfolio_intelligence.service import PortfolioIntelligenceService
from .contracts import ExecutionIntent,ExecutionIntentState,TERMINAL_STATES
from .models import ExecutionIntentModel,ExecutionIntentAuditModel
from .repository import ExecutionIntentRepository

def now():return datetime.now(timezone.utc).isoformat()
class ExecutionWorkspaceService:
 def __init__(self,s:Session):self.s=s;self.repo=ExecutionIntentRepository(s)
 def create_from_trade_plan(self,trade_plan_id:str,actor:str,portfolio_id:str|None=None):
  tp=self.s.get(TradePlanModel,trade_plan_id)
  if not tp:raise KeyError('Trade plan not found')
  if tp.state!='PAPER_READY':raise ValueError('Trade plan must be PAPER_READY')
  old=self.repo.by_trade_plan(tp.trade_plan_id,tp.version)
  if old:return self.dto(old)
  portfolio_id=portfolio_id or tp.account_id
  binding=self.s.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id==portfolio_id,BrokerAccountBindingModel.broker_name=='INTERACTIVE_BROKERS'))
  if binding:
   from trading_ai.broker.ibkr.database_models import BrokerOrderControlModel
   ctl=self.s.get(BrokerOrderControlModel,portfolio_id);enabled=bool(ctl and ctl.paper_order_submission_enabled)
   control={'portfolio_id':portfolio_id,'binding_status':binding.status,'environment':binding.broker_environment,'paper_order_submission_enabled':enabled,'live_trading_enabled':bool(binding.live_trading_enabled),'read_only':bool(binding.read_only),'status':'PAPER_ORDER_ROUTING_ENABLED' if enabled else 'PAPER_ORDER_ROUTING_DISABLED'}
  else:control={'status':'BINDING_NOT_FOUND','paper_order_submission_enabled':False,'live_trading_enabled':False,'environment':'PAPER','read_only':True}
  snap=self.s.scalar(select(BrokerAccountSnapshotModel).where(BrokerAccountSnapshotModel.portfolio_id==portfolio_id).order_by(BrokerAccountSnapshotModel.captured_at.desc()).limit(1))
  buying_power=float(snap.buying_power) if snap else None
  legs=list(tp.legs_json);notional=round(sum(abs(float(x.get('limit_price',0))*int(x.get('quantity',0))*100) for x in legs),2)
  actions={str(x.get('side','')).upper() for x in legs};described=all(x.get('expiry') and x.get('strike') is not None and float(x.get('strike',0))>0 and x.get('option_right') and x.get('limit_price') is not None and float(x.get('limit_price',0))>0 and float(x.get('quantity',0))>0 and bool(str(x.get('option_symbol') or '').strip()) for x in legs);combo_supported=len(legs)==1 or (2<=len(legs)<=4 and actions=={'BUY','SELL'} and described)
  checks={'trade_plan_paper_ready':True,'paper_environment':bool(binding and binding.broker_environment=='PAPER' and not binding.live_trading_enabled),'paper_routing_enabled':bool(control.get('paper_order_submission_enabled')),'has_legs':bool(legs),'atomic_combo_supported':combo_supported,'risk_within_buying_power':buying_power is None or tp.max_loss<=buying_power,'defined_risk':bool(tp.validation_json.get('defined_risk',False))}
  warnings=[]
  if buying_power is None:warnings.append('Latest broker buying-power snapshot is not available.')
  if not all(bool(str(x.get('option_symbol') or '').strip()) for x in legs):warnings.append('Every option leg must reference an exact Polygon option_symbol before approval.')
  if len(legs)>1:warnings.append('Multi-leg strategy will be submitted atomically as an IBKR BAG combo after contract-ID resolution.')
  valid=all(checks.values())
  validation={'valid':valid,'checks':checks,'warnings':warnings,'estimated_notional':notional,'max_loss':tp.max_loss,'buying_power':buying_power}
  state='VALIDATED' if valid else 'PAPER_READY';ts=now();iid=f'XI-{uuid4().hex.upper()}'
  order_request={'environment':'PAPER','live_trading_enabled':False,'portfolio_id':portfolio_id,'account_id':tp.account_id,'symbol':tp.symbol,'strategy':tp.strategy,'legs':legs,'order_type':'LMT','time_in_force':'DAY','transmit':True,'confirmation_required':f'SUBMIT PAPER INTENT {iid}'}
  m=ExecutionIntentModel(execution_intent_id=iid,trade_plan_id=tp.trade_plan_id,trade_plan_version=tp.version,opportunity_id=tp.opportunity_id,portfolio_id=portfolio_id,account_id=tp.account_id,symbol=tp.symbol,strategy=tp.strategy,state=state,version=1,max_loss=tp.max_loss,legs_json=legs,order_request_json=order_request,validation_json=validation,broker_json={'routing_control':control},metadata_json={'paper_only':True,'source':'M56_TRADE_PLAN'},created_by=actor,created_at=ts,updated_at=ts,submitted_at=None,terminal_at=None)
  self.repo.add(m);self._audit(m,None,state,'EXECUTION_INTENT_CREATED',actor,'Created from governed PAPER_READY trade plan',{'validation':validation});self.s.commit();return self.dto(m)
 def transition(self,id,expected_version,target,actor,reason):
  m=self._get_version(id,expected_version);target=ExecutionIntentState(target).value
  allowed={'PAPER_READY':['VALIDATED','REJECTED','EXPIRED'],'VALIDATED':['APPROVED','REJECTED','EXPIRED'],'APPROVED':['REJECTED','EXPIRED'],'SUBMITTED':['CANCEL_REQUESTED'],'ACKNOWLEDGED':['CANCEL_REQUESTED'],'PARTIALLY_FILLED':['CANCEL_REQUESTED'],'CANCEL_REQUESTED':[],'FILLED':[],'CANCELLED':[],'REJECTED':[],'EXPIRED':[]}
  if target not in allowed.get(m.state,[]):raise ValueError(f'Invalid transition {m.state} -> {target}')
  if target in ('VALIDATED','APPROVED') and not m.validation_json.get('valid'):raise ValueError('Execution intent has failed validation checks')
  previous=m.state;m.version+=1;m.state=target;m.updated_at=now();m.terminal_at=m.updated_at if target in TERMINAL_STATES else None
  self._audit(m,previous,target,'EXECUTION_INTENT_TRANSITIONED',actor,reason,{});self.s.commit();return self.dto(m)
 def submit(self,id,expected_version,actor,reason,confirmation):
  m=self._get_version(id,expected_version)
  if m.state!='APPROVED':raise ValueError('Execution intent must be APPROVED')
  expected=f'SUBMIT PAPER INTENT {m.execution_intent_id}'
  if confirmation.strip()!=expected:raise ValueError(f'confirmation must exactly equal: {expected}')
  binding=self.s.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id==m.portfolio_id,BrokerAccountBindingModel.broker_name=='INTERACTIVE_BROKERS'))
  if not binding:raise KeyError('IBKR binding not found')
  legs=list(m.legs_json);self._validate_polygon_contracts(m.symbol,legs);aggregate_id=f'M59-{m.execution_intent_id}';client_id=f'M59-CLIENT-{m.execution_intent_id}'
  combo_quantity=self._combo_quantity(legs) if len(legs)>1 else float(legs[0]['quantity'])
  signed_net_price=self._signed_combo_price(legs) if len(legs)>1 else float(legs[0]['limit_price'])
  canonical=self.s.get(CanonicalOrderModel,aggregate_id)
  if canonical is None:
   ts=now();canonical=CanonicalOrderModel(aggregate_id=aggregate_id,client_order_id=client_id,account_id=m.portfolio_id,idempotency_key=aggregate_id,order_type='LMT',time_in_force='DAY',state='VALIDATED',version=1,total_quantity=combo_quantity,filled_quantity=0,remaining_quantity=combo_quantity,average_fill_price=None,limit_price=signed_net_price,stop_price=None,outside_regular_hours=False,strategy_name=m.strategy,broker_order_id=None,parent_aggregate_id=None,root_aggregate_id=aggregate_id,replace_count=0,legs_json=legs,created_at=ts,updated_at=ts,terminal_at=None,last_event_id=None,metadata_json={'execution_intent_id':m.execution_intent_id,'paper_only':True,'atomic_combo':len(legs)>1});self.s.add(canonical);self.s.flush()
  self.s.commit()
  transport=IbapiPaperOrderTransport();service=IbkrPaperOrderService(lambda:__import__('trading_ai.database.session',fromlist=['SessionLocal']).SessionLocal(),transport)
  resolved_legs=[]
  try:
   connection=transport.connect(IbkrPaperConnectionConfig(host=binding.host,port=binding.port,client_id=binding.client_id,environment='PAPER',expected_account_id=binding.broker_account_id,timeout_seconds=15,read_only=False))
   if len(legs)==1:
    leg=legs[0]
    resolved=transport.resolve_option_contract(symbol=m.symbol,expiry=str(leg['expiry']),strike=float(leg['strike']),right=str(leg['option_right']),currency=binding.base_currency or 'USD',exchange='SMART',multiplier='100',local_symbol=str(leg.get('option_symbol') or ''))
    request=IbkrPaperOrderRequest(aggregate_id=aggregate_id,client_order_id=client_id,portfolio_id=m.portfolio_id,broker_account_id=binding.broker_account_id,symbol=m.symbol,security_type='OPT',side=str(leg['side']),quantity=float(leg['quantity']),order_type='LMT',time_in_force='DAY',limit_price=float(leg['limit_price']),currency=binding.base_currency or 'USD',exchange=resolved.exchange or 'SMART',contract_id=resolved.contract_id,local_symbol=resolved.local_symbol,expiry=str(leg.get('expiry') or '').replace('-',''),strike=float(leg.get('strike') or 0),right='C' if str(leg.get('option_right')).upper() in {'CALL','C'} else 'P',multiplier=resolved.multiplier or '100',transmit=True,metadata={'execution_intent_id':m.execution_intent_id,'paper_only':True,'contract_qualified':True,'contract_source':'IBKR_CONTRACT_DETAILS'})
    resolved_legs.append(resolved)
    result=service.submit(request)
   else:
    base_quantity=self._combo_quantity(legs)
    for leg in legs:
     resolved=transport.resolve_option_contract(symbol=m.symbol,expiry=str(leg['expiry']),strike=float(leg['strike']),right=str(leg['option_right']),currency=binding.base_currency or 'USD',exchange='SMART',multiplier='100',local_symbol=str(leg.get('option_symbol') or ''))
     resolved_legs.append(IbkrPaperComboLegRequest(contract_id=resolved.contract_id,ratio=max(1,int(round(float(leg['quantity'])/base_quantity))),action=str(leg['side']).upper(),exchange=resolved.exchange,symbol=m.symbol,local_symbol=resolved.local_symbol,expiry=str(leg['expiry']),strike=float(leg['strike']),right=str(leg['option_right']).upper(),multiplier=resolved.multiplier))
    request=IbkrPaperComboOrderRequest(aggregate_id=aggregate_id,client_order_id=client_id,portfolio_id=m.portfolio_id,broker_account_id=binding.broker_account_id,symbol=m.symbol,quantity=base_quantity,combo_legs=tuple(resolved_legs),order_type='LMT',time_in_force='DAY',limit_price=signed_net_price,currency=binding.base_currency or 'USD',exchange='SMART',metadata={'execution_intent_id':m.execution_intent_id,'paper_only':True,'atomic_combo':True,'strategy':m.strategy})
    result=service.submit_combo(request)
  finally:transport.disconnect()
  broker_status=str(result.get('status') or '').upper();target='REJECTED' if broker_status in {'REJECTED','INACTIVE'} else ('ACKNOWLEDGED' if broker_status in {'PRESUBMITTED','ACKNOWLEDGED','WORKING'} else 'SUBMITTED')
  previous=m.state;m.version+=1;m.state=target;m.submitted_at=now();m.updated_at=m.submitted_at;m.terminal_at=m.updated_at if target in TERMINAL_STATES else None;m.broker_json={**m.broker_json,'connection':connection,'submission':result,'aggregate_id':aggregate_id,'atomic_combo':len(legs)>1,'resolved_combo_legs':[x.__dict__ for x in resolved_legs]};self._audit(m,previous,m.state,'PAPER_ORDER_REJECTED' if target=='REJECTED' else 'PAPER_ORDER_SUBMITTED',actor,reason,{'broker':result,'atomic_combo':len(legs)>1});self.s.commit();return self.dto(m)
 def synchronize(self,id,actor):
  m=self.repo.get(id)
  if not m:raise KeyError('Execution intent not found')
  binding=self.s.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id==m.portfolio_id,BrokerAccountBindingModel.broker_name=='INTERACTIVE_BROKERS'))
  if not binding:raise KeyError('IBKR binding not found')
  transport=IbapiPaperOrderTransport();service=IbkrPaperOrderService(lambda:__import__('trading_ai.database.session',fromlist=['SessionLocal']).SessionLocal(),transport)
  try:
   transport.connect(IbkrPaperConnectionConfig(host=binding.host,port=binding.port,client_id=binding.client_id,environment='PAPER',expected_account_id=binding.broker_account_id,timeout_seconds=15,read_only=False));sync=service.synchronize(m.portfolio_id)
  finally:transport.disconnect()
  aggregate=m.broker_json.get('aggregate_id');row=self.s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.aggregate_id==aggregate)) if aggregate else None
  if row:
   mapped={'SUBMITTED':'SUBMITTED','PRESUBMITTED':'ACKNOWLEDGED','FILLED':'FILLED','CANCELLED':'CANCELLED','CANCELED':'CANCELLED','CANCEL_REQUESTED':'CANCEL_REQUESTED','REJECTED':'REJECTED','INACTIVE':'REJECTED'}.get(row.status.upper(),m.state)
   if 0<row.filled_quantity<row.quantity:mapped='PARTIALLY_FILLED'
   if mapped!=m.state:
    previous=m.state;m.version+=1;m.state=mapped;m.updated_at=now();m.terminal_at=m.updated_at if mapped in TERMINAL_STATES else None;m.broker_json={**m.broker_json,'last_sync':sync,'order_status':{'status':row.status,'filled_quantity':row.filled_quantity,'remaining_quantity':row.remaining_quantity,'average_fill_price':row.average_fill_price}};self._audit(m,previous,mapped,'BROKER_STATUS_SYNCHRONIZED',actor,'Synchronized execution intent with IBKR paper order',{'sync':sync})
    if mapped=='FILLED':self._open_position(m,row,actor)
    self.s.commit()
  return self.dto(m)
 def cancel(self,id,expected_version,actor,reason):
  m=self._get_version(id,expected_version);aggregate=m.broker_json.get('aggregate_id')
  if not aggregate:raise ValueError('Intent has not been submitted')
  binding=self.s.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id==m.portfolio_id,BrokerAccountBindingModel.broker_name=='INTERACTIVE_BROKERS'))
  transport=IbapiPaperOrderTransport();service=IbkrPaperOrderService(lambda:__import__('trading_ai.database.session',fromlist=['SessionLocal']).SessionLocal(),transport)
  try:
   transport.connect(IbkrPaperConnectionConfig(host=binding.host,port=binding.port,client_id=binding.client_id,environment='PAPER',expected_account_id=binding.broker_account_id,timeout_seconds=15,read_only=False));result=service.cancel(m.portfolio_id,aggregate)
  finally:transport.disconnect()
  previous=m.state;m.version+=1;m.state='CANCEL_REQUESTED';m.updated_at=now();m.broker_json={**m.broker_json,'cancel':result};self._audit(m,previous,m.state,'PAPER_ORDER_CANCEL_REQUESTED',actor,reason,{'broker':result});self.s.commit();return self.dto(m)
 @staticmethod
 def _combo_quantity(legs):
  from math import gcd
  quantities=[max(1,int(round(float(x.get('quantity',1))))) for x in legs]
  value=quantities[0]
  for qty in quantities[1:]:value=gcd(value,qty)
  return float(max(1,value))
 @staticmethod
 def _signed_combo_price(legs):
  base=ExecutionWorkspaceService._combo_quantity(legs)
  total=0.0
  for leg in legs:
   ratio=float(leg.get('quantity',1))/base
   sign=1.0 if str(leg.get('side','BUY')).upper()=='BUY' else -1.0
   total += sign*ratio*float(leg.get('limit_price',0))
  return round(total,4)
 def _open_position(self,m,row,actor):
  qty=float(row.filled_quantity);price=float(row.average_fill_price or 0);mark={'mark_price':price,'quantity':qty,'market_value':price*qty*100,'unrealized_pnl':0,'unrealized_return_pct':0,'delta':0,'gamma':0,'theta':0,'vega':0,'days_to_expiry':None}
  PortfolioIntelligenceService(self.s).open_from_trade_plan(m.trade_plan_id,m.portfolio_id,mark,actor,execution_id=m.execution_intent_id)
 def _get_version(self,id,v):
  m=self.repo.get(id)
  if not m:raise KeyError('Execution intent not found')
  if m.version!=v:raise RuntimeError(f'Execution intent version conflict: expected {v}, actual {m.version}')
  return m

 def _validate_polygon_contracts(self,symbol,legs):
  query=text("SELECT 1 FROM option_contract_history WHERE underlying_symbol=:symbol AND option_symbol=:option_symbol AND expiry=CAST(:expiry AS date) AND strike=:strike AND UPPER(option_type) IN (:option_type,:option_right) ORDER BY quote_date DESC LIMIT 1")
  for index,leg in enumerate(legs,1):
   option_symbol=str(leg.get('option_symbol') or '').strip()
   expiry=str(leg.get('expiry') or '').strip()
   strike=float(leg.get('strike') or 0)
   right=str(leg.get('option_right') or '').upper().strip()
   if not option_symbol:raise ValueError(f'Option leg {index} has no Polygon option_symbol; rebuild the trade plan from an approved option-chain contract')
   if not expiry or strike<=0 or right not in {'CALL','PUT','C','P'}:raise ValueError(f'Option leg {index} has incomplete contract identity: expiry={expiry!r}, strike={strike}, right={right!r}')
   normalized_expiry=expiry if '-' in expiry else f'{expiry[:4]}-{expiry[4:6]}-{expiry[6:8]}' if len(expiry)==8 else expiry
   normalized_right='CALL' if right in {'CALL','C'} else 'PUT'
   found=self.s.execute(query,{'symbol':str(symbol).upper(),'option_symbol':option_symbol,'expiry':normalized_expiry,'strike':strike,'option_type':normalized_right,'option_right':normalized_right[0]}).first()
   if not found:raise ValueError(f'Approved Polygon option contract not found for leg {index}: {option_symbol} ({symbol} {normalized_expiry} {normalized_right} {strike})')
 def _audit(self,m,previous,new,event,actor,reason,payload):self.repo.add(ExecutionIntentAuditModel(event_id=f'XEA-{uuid4().hex.upper()}',execution_intent_id=m.execution_intent_id,execution_intent_version=m.version,event_type=event,previous_state=previous,new_state=new,actor=actor,reason=reason,event_timestamp=now(),payload_json=payload))
 @staticmethod
 def dto(m):return ExecutionIntent(m.execution_intent_id,m.trade_plan_id,m.trade_plan_version,m.opportunity_id,m.portfolio_id,m.account_id,m.symbol,m.strategy,ExecutionIntentState(m.state),m.version,tuple(m.legs_json),dict(m.order_request_json),dict(m.validation_json),dict(m.broker_json),m.created_by,m.created_at,m.updated_at,m.submitted_at,m.terminal_at,dict(m.metadata_json)).to_dict()
