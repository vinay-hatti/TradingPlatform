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
 VERSION='M73.0.7-GOVERNED-EXECUTION-RETRY-REARM-1.0+M74.11-WORKING-ORDER-PRICE-TELEMETRY-1.0+M74.12-ADAPTIVE-MARKET-STATE-CHASE-1.0'
 RETRYABLE_TERMINAL_STATES={'REJECTED','CANCELLED','EXPIRED'}
 def __init__(self,s:Session):self.s=s;self.repo=ExecutionIntentRepository(s)
 def create_from_trade_plan(self,trade_plan_id:str,actor:str,portfolio_id:str|None=None):
  tp=self.s.get(TradePlanModel,trade_plan_id)
  if not tp:raise KeyError('Trade plan not found')
  if tp.state!='PAPER_READY':raise ValueError('Trade plan must be PAPER_READY')
  old=self.repo.by_trade_plan(tp.trade_plan_id,tp.version)
  if old:
   if old.state in self.RETRYABLE_TERMINAL_STATES:
    self._assert_retry_broker_terminal(old);self._assert_no_existing_position(old)
    return self._create_attempt(tp,actor,portfolio_id or tp.account_id,parent=old,retry_reason='Re-opened terminal execution from PAPER_READY trade plan')
   refreshed_metadata=self._intent_metadata(tp)
   if refreshed_metadata!=dict(old.metadata_json or {}):
    old.version += 1;old.metadata_json=refreshed_metadata;old.updated_at=now()
    self._audit(old,old.state,old.state,'EXECUTION_INTENT_MANAGEMENT_REFRESHED',actor,'Refreshed M62 decision and dynamic-management handoff from trade plan',{'management_plan_available':bool(refreshed_metadata.get('dynamic_management'))})
    self.s.commit()
   return self.dto(old)
  return self._create_attempt(tp,actor,portfolio_id or tp.account_id,parent=None,retry_reason=None)

 def retry_terminal(self,id,expected_version,actor,reason):
  parent=self._get_version(id,expected_version)
  if parent.state=='CANCEL_REQUESTED':raise ValueError('Retry is blocked until IBKR confirms CANCELLED')
  if parent.state not in self.RETRYABLE_TERMINAL_STATES:raise ValueError(f'Execution intent state {parent.state} is not retryable')
  self._assert_retry_broker_terminal(parent)
  self._assert_no_existing_position(parent)
  tp=self.s.get(TradePlanModel,parent.trade_plan_id)
  if not tp:raise KeyError('Trade plan not found')
  if int(tp.version)!=int(parent.trade_plan_version):raise ValueError('Trade plan version changed; create execution from the current PAPER_READY plan instead')
  if tp.state!='PAPER_READY':raise ValueError('Trade plan must remain PAPER_READY for execution retry')
  return self._create_attempt(tp,actor,parent.portfolio_id,parent=parent,retry_reason=reason)

 def _create_attempt(self,tp,actor,portfolio_id,parent=None,retry_reason=None):
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
  certification=dict((tp.execution_intent_json or {}).get('trade_plan_certification') or {});certified=(not (tp.execution_intent_json or {}).get('m62_lineage')) or certification.get('status')=='PASS'
  checks={'trade_plan_paper_ready':True,'paper_environment':bool(binding and binding.broker_environment=='PAPER' and not binding.live_trading_enabled),'paper_routing_enabled':bool(control.get('paper_order_submission_enabled')),'has_legs':bool(legs),'atomic_combo_supported':combo_supported,'risk_within_buying_power':buying_power is None or tp.max_loss<=buying_power,'defined_risk':bool(tp.validation_json.get('defined_risk',False)),'institutional_trade_plan_certified':certified}
  warnings=[]
  if buying_power is None:warnings.append('Latest broker buying-power snapshot is not available.')
  if not all(bool(str(x.get('option_symbol') or '').strip()) for x in legs):warnings.append('Every option leg must reference an exact Polygon option_symbol before approval.')
  if len(legs)>1:warnings.append('Multi-leg strategy will be submitted atomically as an IBKR BAG combo after contract-ID resolution.')
  valid=all(checks.values());validation={'valid':valid,'checks':checks,'warnings':warnings,'estimated_notional':notional,'max_loss':tp.max_loss,'buying_power':buying_power}
  state='VALIDATED' if valid else 'PAPER_READY';ts=now();iid=f'XI-{uuid4().hex.upper()}';attempt=self.repo.next_attempt(tp.trade_plan_id,tp.version)
  order_request={'environment':'PAPER','live_trading_enabled':False,'portfolio_id':portfolio_id,'account_id':tp.account_id,'symbol':tp.symbol,'strategy':tp.strategy,'legs':legs,'order_type':'LMT','time_in_force':'DAY','transmit':True,'confirmation_required':f'SUBMIT PAPER INTENT {iid}'}
  metadata={**self._intent_metadata(tp),'execution_attempt':attempt,'parent_execution_intent_id':getattr(parent,'execution_intent_id',None),'retry_reason':retry_reason,'retry_requires_fresh_preflight':True}
  m=ExecutionIntentModel(execution_intent_id=iid,trade_plan_id=tp.trade_plan_id,trade_plan_version=tp.version,execution_attempt=attempt,parent_execution_intent_id=getattr(parent,'execution_intent_id',None),retry_reason=retry_reason,opportunity_id=tp.opportunity_id,portfolio_id=portfolio_id,account_id=tp.account_id,symbol=tp.symbol,strategy=tp.strategy,state=state,version=1,max_loss=tp.max_loss,legs_json=legs,order_request_json=order_request,validation_json=validation,broker_json={'routing_control':control},metadata_json=metadata,created_by=actor,created_at=ts,updated_at=ts,submitted_at=None,terminal_at=None)
  self.repo.add(m);event='EXECUTION_RETRY_CREATED' if parent else 'EXECUTION_INTENT_CREATED';payload={'validation':validation,'execution_attempt':attempt,'parent_execution_intent_id':getattr(parent,'execution_intent_id',None),'retry_reason':retry_reason}
  self._audit(m,None,state,event,actor,retry_reason or 'Created from governed PAPER_READY trade plan',payload);self.s.commit();return self.dto(m)

 def _assert_retry_broker_terminal(self,parent):
  aggregate=str((parent.broker_json or {}).get('aggregate_id') or '')
  if not aggregate:return
  row=self.s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.aggregate_id==aggregate))
  if not row:return
  status=str(row.status or '').upper()
  if status in {'SUBMITTED','PRESUBMITTED','ACKNOWLEDGED','WORKING','AWAITING_BROKER_ACK','PENDING_SUBMIT','PENDINGSUBMIT','PARTIALLY_FILLED','CANCEL_REQUESTED'} or float(row.remaining_quantity or 0)>0 and status not in {'REJECTED','CANCELLED','CANCELED','INACTIVE','FILLED'}:
   raise ValueError(f'Retry blocked: broker order is not terminal (status={status}, remaining={float(row.remaining_quantity or 0)})')
  if status=='FILLED' or float(row.filled_quantity or 0)>=float(row.quantity or 0)>0:raise ValueError('Retry blocked: broker order filled; reconcile the position instead')

 def _assert_no_existing_position(self,parent):
  try:
   from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel
   legs=list(parent.legs_json or []);contracts=list((parent.broker_json or {}).get('resolved_combo_legs') or [])
   contract_ids={int(x.get('contract_id') or 0) for x in contracts if int(x.get('contract_id') or 0)>0}
   q=select(BrokerCurrentPositionModel).where(BrokerCurrentPositionModel.portfolio_id==parent.portfolio_id,BrokerCurrentPositionModel.active==True)
   if contract_ids:q=q.where(BrokerCurrentPositionModel.contract_id.in_(contract_ids))
   else:q=q.where(BrokerCurrentPositionModel.symbol==parent.symbol)
   pos=self.s.scalar(q.limit(1))
   if pos:raise ValueError(f'Retry blocked: an active broker position already exists for {parent.symbol} (contract_id={pos.contract_id})')
  except ImportError:
   pass

 def _intent_metadata(self,tp):
  intent_payload=dict(tp.execution_intent_json or {})
  metadata={
   'paper_only':True,
   'source':'M56_TRADE_PLAN',
   'm62_lineage':dict(intent_payload.get('m62_lineage') or {}),
   'underlying_thesis':dict(intent_payload.get('underlying_thesis') or {}),
   'dynamic_management':dict(intent_payload.get('dynamic_management') or {}),
   'decision_snapshot_id':intent_payload.get('decision_snapshot_id'),
   'decision_state_hash':intent_payload.get('decision_state_hash'),
   'trade_plan_certification':dict(intent_payload.get('trade_plan_certification') or {}),
  }
  try:
   from trading_ai.institutional_options.models import InstitutionalOptionHandoffModel
   handoff=self.s.scalar(select(InstitutionalOptionHandoffModel).where(InstitutionalOptionHandoffModel.trade_plan_id==tp.trade_plan_id))
   if handoff:
    handoff_payload=dict(handoff.payload_json or {})
    metadata.update({
     'source':'M62_INSTITUTIONAL_OPTIONS',
     'institutional_options_handoff_id':handoff.handoff_id,
     'm62_lineage':dict(handoff.lineage_json or {}) or metadata['m62_lineage'],
     'underlying_thesis':dict(handoff_payload.get('thesis') or {}) or metadata['underlying_thesis'],
     'dynamic_management':dict(handoff_payload.get('dynamic_management') or {}) or metadata['dynamic_management'],
     'trade_plan_certification':dict(handoff_payload.get('trade_plan_certification') or {}) or metadata['trade_plan_certification'],
     'governed_overrides':dict(handoff.overrides_json or {}),
    })
  except Exception:
   pass
  metadata['management_plan_available']=bool(metadata.get('dynamic_management'))
  metadata['management_activation']='AFTER_FILL'
  return metadata
 def transition(self,id,expected_version,target,actor,reason):
  m=self._get_version(id,expected_version);target=ExecutionIntentState(target).value
  allowed={'PAPER_READY':['VALIDATED','REJECTED','EXPIRED'],'VALIDATED':['APPROVED','REJECTED','EXPIRED'],'APPROVED':['REJECTED','EXPIRED'],'SUBMITTED':['CANCEL_REQUESTED'],'ACKNOWLEDGED':['CANCEL_REQUESTED'],'PARTIALLY_FILLED':['CANCEL_REQUESTED'],'CANCEL_REQUESTED':[],'FILLED':[],'CANCELLED':[],'REJECTED':[],'EXPIRED':[]}
  if target not in allowed.get(m.state,[]):raise ValueError(f'Invalid transition {m.state} -> {target}')
  if target in ('VALIDATED','APPROVED') and not m.validation_json.get('valid'):raise ValueError('Execution intent has failed validation checks')
  previous=m.state;m.version+=1;m.state=target;m.updated_at=now();m.terminal_at=m.updated_at if target in TERMINAL_STATES else None
  audit_payload={}
  if target=='APPROVED':
   from trading_ai.execution_intelligence.policy import load_execution_intelligence_policy
   p=load_execution_intelligence_policy();reference=self._signed_combo_price(list(m.legs_json));drift=p.max_price_drift_pct/100.0
   envelope={'reference_price':reference,'max_adverse_drift_pct':p.max_price_drift_pct,'maximum_debit':round(reference*(1+drift),4) if reference>=0 else None,'minimum_credit':round(abs(reference)*(1-drift),4) if reference<0 else None,'approved_max_loss':float(m.max_loss),'created_at':m.updated_at,'policy_version':p.policy_version}
   m.metadata_json={**dict(m.metadata_json or {}),'execution_approval_envelope':envelope};audit_payload={'execution_approval_envelope':envelope}
  self._audit(m,previous,target,'EXECUTION_INTENT_TRANSITIONED',actor,reason,audit_payload);self.s.commit();return self.dto(m)
 def submit(self,id,expected_version,actor,reason,confirmation):
  m=self._get_version(id,expected_version)
  if m.state!='APPROVED':raise ValueError('Execution intent must be APPROVED')
  expected=f'SUBMIT PAPER INTENT {m.execution_intent_id}'
  if confirmation.strip()!=expected:raise ValueError(f'confirmation must exactly equal: {expected}')
  from trading_ai.execution_intelligence.service import ExecutionIntelligenceService
  execution_gate=ExecutionIntelligenceService(self.s).preflight(m.execution_intent_id,actor,reason)
  if execution_gate['decision']!='EXECUTE' or not execution_gate['validation_json'].get('valid'):
   failed=[k for k,v in execution_gate['validation_json'].get('checks',{}).items() if not v]
   raise ValueError(f"Execution intelligence blocked routing: {execution_gate['decision']}; failed checks: {', '.join(failed) or 'unknown'}")
  binding=self.s.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id==m.portfolio_id,BrokerAccountBindingModel.broker_name=='INTERACTIVE_BROKERS'))
  if not binding:raise KeyError('IBKR binding not found')
  legs=list(m.legs_json);self._validate_polygon_contracts(m.symbol,legs);aggregate_id=f'M59-{m.execution_intent_id}';client_id=f'M59-CLIENT-{m.execution_intent_id}'
  combo_quantity=self._combo_quantity(legs) if len(legs)>1 else float(legs[0]['quantity'])
  signed_net_price=float(execution_gate['governed_limit_price'])
  broker_limit_price=abs(signed_net_price) if len(legs)==1 else signed_net_price
  live_leg_map={str(x.get('option_symbol')):x for x in execution_gate.get('quotes_json',{}).get('live_legs',[])}
  canonical=self.s.get(CanonicalOrderModel,aggregate_id)
  if canonical is None:
   ts=now();canonical=CanonicalOrderModel(aggregate_id=aggregate_id,client_order_id=client_id,account_id=m.portfolio_id,idempotency_key=aggregate_id,order_type='LMT',time_in_force='DAY',state='VALIDATED',version=1,total_quantity=combo_quantity,filled_quantity=0,remaining_quantity=combo_quantity,average_fill_price=None,limit_price=broker_limit_price,stop_price=None,outside_regular_hours=False,strategy_name=m.strategy,broker_order_id=None,parent_aggregate_id=None,root_aggregate_id=aggregate_id,replace_count=0,legs_json=legs,created_at=ts,updated_at=ts,terminal_at=None,last_event_id=None,metadata_json={'execution_intent_id':m.execution_intent_id,'paper_only':True,'atomic_combo':len(legs)>1});self.s.add(canonical);self.s.flush()
  self.s.commit()
  transport=IbapiPaperOrderTransport();service=IbkrPaperOrderService(lambda:__import__('trading_ai.database.session',fromlist=['SessionLocal']).SessionLocal(),transport)
  resolved_legs=[]
  try:
   connection=transport.connect(IbkrPaperConnectionConfig(host=binding.host,port=binding.port,client_id=binding.client_id,environment='PAPER',expected_account_id=binding.broker_account_id,timeout_seconds=15,read_only=False))
   if len(legs)==1:
    leg=legs[0]
    resolved=transport.resolve_option_contract(symbol=m.symbol,expiry=str(leg['expiry']),strike=float(leg['strike']),right=str(leg['option_right']),currency=binding.base_currency or 'USD',exchange='SMART',multiplier='100',local_symbol=str(leg.get('option_symbol') or ''))
    price_normalization=transport.normalize_option_limit_price(contract_id=resolved.contract_id,price=broker_limit_price,side=str(leg['side']),exchange=resolved.exchange or 'SMART')
    broker_limit_price=float(price_normalization['normalized_price'])
    execution_gate={**dict(execution_gate),'broker_price_normalization':price_normalization,'broker_normalized_limit_price':broker_limit_price}
    canonical.limit_price=broker_limit_price;canonical.updated_at=now();canonical.metadata_json={**dict(canonical.metadata_json or {}),'ibkr_price_normalization':price_normalization}
    request=IbkrPaperOrderRequest(aggregate_id=aggregate_id,client_order_id=client_id,portfolio_id=m.portfolio_id,broker_account_id=binding.broker_account_id,symbol=m.symbol,security_type='OPT',side=str(leg['side']),quantity=float(leg['quantity']),order_type='LMT',time_in_force='DAY',limit_price=broker_limit_price,currency=binding.base_currency or 'USD',exchange=resolved.exchange or 'SMART',contract_id=resolved.contract_id,local_symbol=resolved.local_symbol,expiry=str(leg.get('expiry') or '').replace('-',''),strike=float(leg.get('strike') or 0),right='C' if str(leg.get('option_right')).upper() in {'CALL','C'} else 'P',multiplier=resolved.multiplier or '100',transmit=True,metadata={'execution_intent_id':m.execution_intent_id,'paper_only':True,'contract_qualified':True,'contract_source':'IBKR_CONTRACT_DETAILS','execution_snapshot_id':execution_gate['execution_snapshot_id'],'execution_intelligence':'PASS','ibkr_price_normalization':price_normalization})
    resolved_legs.append(resolved)
    result=service.submit(request)
   else:
    base_quantity=self._combo_quantity(legs)
    for leg in legs:
     resolved=transport.resolve_option_contract(symbol=m.symbol,expiry=str(leg['expiry']),strike=float(leg['strike']),right=str(leg['option_right']),currency=binding.base_currency or 'USD',exchange='SMART',multiplier='100',local_symbol=str(leg.get('option_symbol') or ''))
     resolved_legs.append(IbkrPaperComboLegRequest(contract_id=resolved.contract_id,ratio=max(1,int(round(float(leg['quantity'])/base_quantity))),action=str(leg['side']).upper(),exchange=resolved.exchange,symbol=m.symbol,local_symbol=resolved.local_symbol,expiry=str(leg['expiry']),strike=float(leg['strike']),right=str(leg['option_right']).upper(),multiplier=resolved.multiplier))
    request=IbkrPaperComboOrderRequest(aggregate_id=aggregate_id,client_order_id=client_id,portfolio_id=m.portfolio_id,broker_account_id=binding.broker_account_id,symbol=m.symbol,quantity=base_quantity,combo_legs=tuple(resolved_legs),order_type='LMT',time_in_force='DAY',limit_price=signed_net_price,currency=binding.base_currency or 'USD',exchange='SMART',metadata={'execution_intent_id':m.execution_intent_id,'paper_only':True,'atomic_combo':True,'strategy':m.strategy,'execution_snapshot_id':execution_gate['execution_snapshot_id'],'execution_intelligence':'PASS'})
    result=service.submit_combo(request)
  finally:transport.disconnect()
  broker_status=str(result.get('status') or '').upper();target='REJECTED' if broker_status in {'REJECTED','INACTIVE'} else ('ACKNOWLEDGED' if broker_status in {'PRESUBMITTED','ACKNOWLEDGED','WORKING'} else 'SUBMITTED')
  previous=m.state;m.version+=1;m.state=target;m.submitted_at=now();m.updated_at=m.submitted_at;m.terminal_at=m.updated_at if target in TERMINAL_STATES else None;m.broker_json={**m.broker_json,'connection':connection,'submission':result,'aggregate_id':aggregate_id,'atomic_combo':len(legs)>1,'resolved_combo_legs':[x.__dict__ for x in resolved_legs],'execution_intelligence':execution_gate};self._audit(m,previous,m.state,'PAPER_ORDER_REJECTED' if target=='REJECTED' else 'PAPER_ORDER_SUBMITTED',actor,reason,{'broker':result,'atomic_combo':len(legs)>1});self.s.flush()
  from trading_ai.execution_intelligence.service import ExecutionIntelligenceService
  ExecutionIntelligenceService(self.s).record_submission(m,execution_gate,result,broker_limit_price)
  self.s.commit();return self.dto(m)
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
    from trading_ai.execution_intelligence.service import ExecutionIntelligenceService
    ExecutionIntelligenceService(self.s).record_broker_sync(m,row)
    self.s.commit()
  return self.dto(m)

 def reconcile_entry_with_broker_truth(self,id,actor,max_order_age_seconds):
  m=self.repo.get(id)
  if not m:raise KeyError('Execution intent not found')
  aggregate=str((m.broker_json or {}).get('aggregate_id') or '')
  row=self.s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.aggregate_id==aggregate)) if aggregate else None
  if not row:
   return {'execution_intent_id':id,'state':m.state,'eligible':False,'reason':'BROKER_ORDER_MISSING'}
  status=str(row.status or '').upper()
  terminal_map={'FILLED':'FILLED','CANCELLED':'CANCELLED','CANCELED':'CANCELLED','REJECTED':'REJECTED','INACTIVE':'REJECTED'}
  mapped=terminal_map.get(status)
  if 0<float(row.filled_quantity or 0)<float(row.quantity or 0):mapped='PARTIALLY_FILLED'
  if mapped and mapped!=m.state:
   previous=m.state;m.version+=1;m.state=mapped;m.updated_at=now();m.terminal_at=m.updated_at if mapped in TERMINAL_STATES else None
   m.broker_json={**dict(m.broker_json or {}),'order_status':{'status':row.status,'filled_quantity':row.filled_quantity,'remaining_quantity':row.remaining_quantity,'average_fill_price':row.average_fill_price}}
   self._audit(m,previous,mapped,'BROKER_TRUTH_ENTRY_STATE_REPAIRED',actor,'Reconciled stale entry lifecycle from canonical broker truth',{'broker_status':status,'aggregate_id':aggregate})
   if mapped=='FILLED':self._open_position(m,row,actor)
   self.s.commit()
  if m.state in TERMINAL_STATES or mapped in TERMINAL_STATES:
   return {'execution_intent_id':id,'state':m.state,'eligible':False,'reason':'TERMINAL_BROKER_STATE','broker_status':status}
  from datetime import datetime,timezone
  try:
   submitted=datetime.fromisoformat(str(row.submitted_at).replace('Z','+00:00'))
   age=max(0.0,(datetime.now(timezone.utc)-submitted).total_seconds())
  except Exception:age=0.0
  if age>float(max_order_age_seconds or 0):
   # Do not merely expire the local row while leaving the broker order alive.
   # Surface an explicit cancel requirement so M73 can cancel the still-working
   # broker entry and then reconcile the terminal broker status on the next cycle.
   working_for_timeout=status in {'SUBMITTED','PRESUBMITTED','AWAITING_BROKER_ACK','PENDING_SUBMIT','PENDINGSUBMIT','PARTIALLY_FILLED'}
   return {'execution_intent_id':id,'state':m.state,'eligible':False,'cancel_required':bool(working_for_timeout and float(row.remaining_quantity or 0)>0),'reason':'ORDER_AGE_EXCEEDED','broker_status':status,'remaining_quantity':float(row.remaining_quantity or 0),'age_seconds':age}
  working=status in {'SUBMITTED','PRESUBMITTED','AWAITING_BROKER_ACK','PENDING_SUBMIT','PENDINGSUBMIT','PARTIALLY_FILLED'}
  eligible=bool(working and float(row.remaining_quantity or 0)>0 and m.state in {'SUBMITTED','ACKNOWLEDGED','PARTIALLY_FILLED'})
  return {'execution_intent_id':id,'state':m.state,'eligible':eligible,'reason':'WORKING_ENTRY' if eligible else 'NOT_CURRENTLY_WORKING','broker_status':status,'remaining_quantity':float(row.remaining_quantity or 0),'age_seconds':age}
 def reprice_working(self,id,expected_version,actor,reason,confirmation=None,automatic=False):
  from trading_ai.execution_intelligence.entry_chase import advance_coarse_tick,monotonic_broker_candidate,same_price
  m=self._get_version(id,expected_version)
  if m.state not in {'SUBMITTED','ACKNOWLEDGED','PARTIALLY_FILLED'}:raise ValueError('Execution intent must be working or partially filled')
  expected=f'REPRICE PAPER INTENT {m.execution_intent_id}'
  if automatic:
   from trading_ai.execution_intelligence.policy import load_execution_intelligence_policy
   policy=load_execution_intelligence_policy()
   if not policy.automatic_fill_management_enabled:raise ValueError('Automatic entry-fill management is disabled by policy')
   if not str(actor).upper().startswith('M73'):raise ValueError('Automatic repricing requires an M73 system actor')
  elif str(confirmation or '').strip()!=expected:raise ValueError(f'confirmation must exactly equal: {expected}')
  from trading_ai.execution_intelligence.service import ExecutionIntelligenceService
  assessment=ExecutionIntelligenceService(self.s).assess_working(m.execution_intent_id,actor,reason)
  if assessment['recommended_action']!='REPRICE':raise ValueError(f"Working-order intelligence recommends {assessment['recommended_action']}, not REPRICE")
  binding=self.s.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id==m.portfolio_id,BrokerAccountBindingModel.broker_name=='INTERACTIVE_BROKERS'))
  if not binding:raise KeyError('IBKR binding not found')
  aggregate=str(m.broker_json.get('aggregate_id') or '');row=self.s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.aggregate_id==aggregate))
  if not row:raise KeyError('Broker order not found for execution intent')
  legs=list(m.legs_json);resolved=list(m.broker_json.get('resolved_combo_legs') or []);theoretical_signed=float(assessment['governed_limit_price']);theoretical_broker=abs(theoretical_signed) if len(legs)==1 else theoretical_signed
  old_limit=float(row.limit_price or 0);raw=dict(row.raw_json or {});price_normalization=None;coarse_tick=None
  broker_new_limit=theoretical_broker
  transport=IbapiPaperOrderTransport();ack=None
  try:
   transport.connect(IbkrPaperConnectionConfig(host=binding.host,port=binding.port,client_id=binding.client_id,environment='PAPER',expected_account_id=binding.broker_account_id,timeout_seconds=15,read_only=False))
   visibility=transport.prepare_existing_order_for_modify(row.broker_order_id)
   if not visibility.get('visible'):
    event={'at':now(),'actor':actor,'assessment_id':assessment['assessment_id'],'reason':'BROKER_MODIFY_SYNC_ERROR','detail':'Existing broker order is not visible to the modifying API client','broker_order_id':row.broker_order_id,'visibility':visibility}
    errors=list(raw.get('m70_modify_error_history') or []);errors.append(event);row.raw_json={**raw,'m70_modify_error_history':errors,'m70_last_modify_result':event};row.updated_at=event['at'];m.broker_json={**dict(m.broker_json or {}),'last_working_assessment':assessment,'last_entry_fill_result':event};self.s.commit();result=self.dto(m);result['entry_fill_result']={'action':'BROKER_MODIFY_SYNC_ERROR','broker_modified':False,'retryable':True,'detail':event};return result
   if len(legs)==1:
    leg=legs[0];r=resolved[0] if resolved else {};side=str(leg['side']).upper()
    broker_new_limit=monotonic_broker_candidate(side,old_limit,theoretical_broker)
    price_normalization=transport.normalize_option_limit_price(contract_id=int(r.get('contract_id') or 0),price=broker_new_limit,side=side,exchange=str(r.get('exchange') or 'SMART'))
    normalized=float(price_normalization['normalized_price']);inc=float(price_normalization.get('increment') or 0.0)
    normalized=monotonic_broker_candidate(side,old_limit,normalized)
    envelope=dict((assessment.get('snapshot') or {}).get('envelope_json') or {})
    executable=abs(float((assessment.get('snapshot') or {}).get('fresh_executable_price') or 0.0))
    coarse_tick=advance_coarse_tick(side=side,current_price=old_limit,theoretical_price=broker_new_limit,normalized_price=normalized,increment=inc,maximum_debit=envelope.get('maximum_debit'),minimum_credit=envelope.get('minimum_credit'),executable_price=executable)
    broker_new_limit=float(coarse_tick['price'])
    price_normalization={**price_normalization,'monotonic_theoretical_price':broker_new_limit if coarse_tick.get('advanced') else theoretical_broker,'coarse_tick_decision':coarse_tick}
    if same_price(broker_new_limit,old_limit):
     event={'from':old_limit,'to':old_limit,'theoretical_price':theoretical_broker,'assessment_id':assessment['assessment_id'],'at':now(),'actor':actor,'reason':'WAIT_TICK_UNCHANGED','broker_modified':False,'ibkr_price_normalization':price_normalization}
     noops=list(raw.get('m70_noop_reprice_history') or []);noops.append(event);row.raw_json={**raw,'m70_noop_reprice_history':noops,'m70_last_modify_result':event};row.updated_at=event['at'];m.broker_json={**dict(m.broker_json or {}),'last_working_assessment':assessment,'last_entry_fill_result':event};self.s.commit();result=self.dto(m);result['entry_fill_result']={'action':'WAIT_TICK_UNCHANGED','broker_modified':False,'detail':event};return result
    request=IbkrPaperOrderRequest(aggregate_id=aggregate,client_order_id=row.client_order_id,portfolio_id=m.portfolio_id,broker_account_id=binding.broker_account_id,symbol=m.symbol,security_type='OPT',side=side,quantity=float(row.quantity),order_type='LMT',time_in_force='DAY',limit_price=broker_new_limit,currency=binding.base_currency or 'USD',exchange=str(r.get('exchange') or 'SMART'),contract_id=int(r.get('contract_id') or 0),local_symbol=str(r.get('local_symbol') or ''),expiry=str(leg.get('expiry') or '').replace('-',''),strike=float(leg.get('strike') or 0),right='C' if str(leg.get('option_right')).upper() in {'CALL','C'} else 'P',multiplier=str(r.get('multiplier') or '100'),transmit=True,metadata={'execution_intent_id':m.execution_intent_id,'m70_reprice':True,'ibkr_price_normalization':price_normalization})
    transport.modify_order(row.broker_order_id,request)
   else:
    combo=tuple(IbkrPaperComboLegRequest(contract_id=int(r['contract_id']),ratio=int(r.get('ratio') or 1),action=str(r['action']).upper(),exchange=str(r.get('exchange') or 'SMART'),symbol=str(r.get('symbol') or m.symbol),local_symbol=str(r.get('local_symbol') or ''),expiry=str(r.get('expiry') or ''),strike=float(r.get('strike') or 0),right=str(r.get('right') or ''),multiplier=str(r.get('multiplier') or '100')) for r in resolved)
    request=IbkrPaperComboOrderRequest(aggregate_id=aggregate,client_order_id=row.client_order_id,portfolio_id=m.portfolio_id,broker_account_id=binding.broker_account_id,symbol=m.symbol,quantity=float(row.quantity),combo_legs=combo,order_type='LMT',time_in_force='DAY',limit_price=broker_new_limit,currency=binding.base_currency or 'USD',exchange='SMART',metadata={'execution_intent_id':m.execution_intent_id,'m70_reprice':True})
    transport.modify_combo_order(row.broker_order_id,request)
   ack=transport.wait_for_order_acknowledgement(row.broker_order_id)
  finally:transport.disconnect()
  ack_ok=bool((ack or {}).get('acknowledged')) and str((ack or {}).get('status') or '').upper() not in {'REJECTED','INACTIVE'}
  if not ack_ok:
   event={'at':now(),'actor':actor,'assessment_id':assessment['assessment_id'],'reason':'BROKER_MODIFY_SYNC_ERROR','broker_order_id':row.broker_order_id,'attempted_price':broker_new_limit,'broker_acknowledgement':ack,'retryable':int((ack or {}).get('error_code') or 0)==103}
   errors=list(raw.get('m70_modify_error_history') or []);errors.append(event);row.raw_json={**raw,'m70_modify_error_history':errors,'m70_last_reprice_ack':ack,'m70_last_modify_result':event};row.updated_at=event['at'];m.broker_json={**dict(m.broker_json or {}),'last_working_assessment':assessment,'last_entry_fill_result':event};self.s.commit();result=self.dto(m);result['entry_fill_result']={'action':'BROKER_MODIFY_SYNC_ERROR','broker_modified':False,'retryable':bool(event['retryable']),'detail':event};return result
  history=list(raw.get('m70_reprice_history') or []);event={'from':old_limit,'to':broker_new_limit,'theoretical_price':theoretical_broker,'assessment_id':assessment['assessment_id'],'at':now(),'actor':actor,'reason':reason,'broker_modified':True,'reprice_number':int(raw.get('m70_reprice_count',0) or 0)+1,'ibkr_price_normalization':price_normalization if len(legs)==1 else None};history.append(event);row.limit_price=broker_new_limit;row.updated_at=event['at'];row.raw_json={**raw,'m70_reprice_count':event['reprice_number'],'m70_reprice_history':history,'m70_last_reprice_ack':ack,'m70_last_modify_result':event}
  canonical=self.s.get(CanonicalOrderModel,aggregate)
  if canonical:canonical.limit_price=broker_new_limit;canonical.replace_count=int(canonical.replace_count or 0)+1;canonical.updated_at=row.updated_at
  # Flush the new broker price before deriving telemetry so the audit event records the exact post-modification state.
  self.s.flush()
  telemetry=ExecutionIntelligenceService(self.s).working_telemetry(m.execution_intent_id)
  event={**event,'working_order_telemetry':telemetry};row.raw_json={**dict(row.raw_json or {}),'m70_reprice_history':history[:-1]+[event],'m70_last_modify_result':event}
  previous=m.state;m.version+=1;m.updated_at=row.updated_at;m.broker_json={**dict(m.broker_json or {}),'last_working_assessment':assessment,'last_working_order_telemetry':telemetry,'last_reprice':event,'last_entry_fill_result':event};self._audit(m,previous,m.state,'WORKING_ORDER_REPRICED',actor,reason,{'from':old_limit,'to':broker_new_limit,'assessment':assessment,'working_order_telemetry':telemetry,'broker_acknowledgement':ack});self.s.commit();result=self.dto(m);result['entry_fill_result']={'action':'REPRICE','broker_modified':True,'detail':event};return result
 
 def cancel(self,id,expected_version,actor,reason):
  m=self._get_version(id,expected_version);aggregate=m.broker_json.get('aggregate_id')
  if not aggregate:raise ValueError('Intent has not been submitted')
  binding=self.s.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id==m.portfolio_id,BrokerAccountBindingModel.broker_name=='INTERACTIVE_BROKERS'))
  transport=IbapiPaperOrderTransport();service=IbkrPaperOrderService(lambda:__import__('trading_ai.database.session',fromlist=['SessionLocal']).SessionLocal(),transport)
  try:
   transport.connect(IbkrPaperConnectionConfig(host=binding.host,port=binding.port,client_id=binding.client_id,environment='PAPER',expected_account_id=binding.broker_account_id,timeout_seconds=15,read_only=False));result=service.cancel(m.portfolio_id,aggregate)
  finally:transport.disconnect()
  previous=m.state;m.version+=1;m.state='CANCEL_REQUESTED';m.updated_at=now();m.broker_json={**m.broker_json,'cancel':result,'m73_entry_fill_terminal_reason':reason};self._audit(m,previous,m.state,'PAPER_ORDER_CANCEL_REQUESTED',actor,reason,{'broker':result});self.s.commit();return self.dto(m)
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
  position=PortfolioIntelligenceService(self.s).open_from_trade_plan(m.trade_plan_id,m.portfolio_id,mark,actor,execution_id=m.execution_intent_id)
  self._activate_exit_instructions(m,position,actor)
  try:
   from trading_ai.autonomous_position_management import AutonomousPositionManagementService, load_m73_policy
   if load_m73_policy().enabled:AutonomousPositionManagementService(self.s).ensure_position(str(position.get('position_id') or ''),actor=f'm73:{actor}')
  except Exception as exc:
   m.metadata_json={**dict(m.metadata_json or {}),'m73_activation_error':f'{type(exc).__name__}: {exc}'}
 def _activate_exit_instructions(self,m,position,actor):
  from trading_ai.position_management.database_models import PositionExitInstructionModel
  position_id=str(position.get('position_id') or '')
  if not position_id:return
  existing=self.s.scalar(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id==position_id).limit(1))
  if existing:return
  management=dict(m.metadata_json.get('dynamic_management') or {})
  if not management:return
  quantity=max(1,int(round(float(m.broker_json.get('order_status',{}).get('filled_quantity') or 1))))
  ts=now();assessment_id=m.execution_intent_id
  instructions=[]
  stop=management.get('underlying_stop')
  if stop is not None:
   instructions.append(('STRUCTURAL_STOP','CLOSE',quantity,{'trigger_type':'UNDERLYING_PRICE','trigger_value':stop,'trailing_policy':management.get('trailing_policy')}))
  # M75.1: the live Polygon preflight is read-only, but its validated effective
  # target ladder is persisted with broker submission evidence.  Arm only those
  # still-directionally-valid targets after fill; never resurrect a crossed target.
  gate=dict((m.broker_json or {}).get('execution_intelligence') or {})
  gate_evidence=dict(gate.get('evidence_json') or {})
  target_revalidation=dict(gate_evidence.get('target_revalidation') or {})
  targets=list(target_revalidation.get('effective_targets') or management.get('underlying_targets') or [])
  fraction=float(management.get('partial_profit_fraction') or 0.33)
  for index,target in enumerate(targets[:3],1):
   target_quantity=quantity if index==len(targets[:3]) else max(1,int(round(quantity*fraction)))
   instructions.append((f'TARGET_{index}','SCALE_OUT' if index<len(targets[:3]) else 'CLOSE',target_quantity,{'trigger_type':'UNDERLYING_PRICE','trigger_value':target,'target_index':index}))
  if management.get('theta_exit_days_to_expiry') is not None:
   instructions.append(('THETA_EXIT','CLOSE',quantity,{'trigger_type':'DTE','trigger_value':management.get('theta_exit_days_to_expiry')}))
  if management.get('volatility_exit_rule'):
   instructions.append(('VOLATILITY_EXIT','CLOSE',quantity,{'trigger_type':'VOLATILITY_RULE','trigger_value':management.get('volatility_exit_rule')}))
  if management.get('emergency_option_stop_pct') is not None:
   instructions.append(('EMERGENCY_OPTION_STOP','CLOSE',quantity,{'trigger_type':'OPTION_LOSS_PCT','trigger_value':management.get('emergency_option_stop_pct')}))
  for label,action,instruction_quantity,trigger in instructions:
   payload={'label':label,'execution_intent_id':m.execution_intent_id,'trade_plan_id':m.trade_plan_id,'opportunity_id':m.opportunity_id,'dynamic_management':management,**trigger}
   self.s.add(PositionExitInstructionModel(instruction_id=f'PXI-{uuid4().hex.upper()}',assessment_id=assessment_id,position_id=position_id,action=action,quantity=instruction_quantity,status='ARMED',payload=payload,created_at=ts))
  if instructions:
   # Dynamic-management activation is a second governed mutation after the
   # broker-status synchronization event. Advance the intent version so the
   # audit uniqueness invariant remains one event per intent version.
   m.version += 1
   m.metadata_json={**dict(m.metadata_json or {}),'management_activation':'ACTIVE','managed_position_id':position_id,'exit_instruction_count':len(instructions),'exit_instructions_armed_at':ts}
   m.updated_at=ts
   self._audit(m,m.state,m.state,'DYNAMIC_MANAGEMENT_ACTIVATED',actor,'Activated managed position and governed exit instructions after fill',{'position_id':position_id,'instruction_count':len(instructions)})
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
 def dto(m):
  d=ExecutionIntent(m.execution_intent_id,m.trade_plan_id,m.trade_plan_version,m.opportunity_id,m.portfolio_id,m.account_id,m.symbol,m.strategy,ExecutionIntentState(m.state),m.version,tuple(m.legs_json),dict(m.order_request_json),dict(m.validation_json),dict(m.broker_json),m.created_by,m.created_at,m.updated_at,m.submitted_at,m.terminal_at,dict(m.metadata_json)).to_dict()
  d.update({'execution_attempt':int(getattr(m,'execution_attempt',1) or 1),'parent_execution_intent_id':getattr(m,'parent_execution_intent_id',None),'retry_reason':getattr(m,'retry_reason',None),'retryable':str(m.state) in ExecutionWorkspaceService.RETRYABLE_TERMINAL_STATES})
  return d
