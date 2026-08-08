from __future__ import annotations
from datetime import datetime,timezone
from time import sleep
from uuid import uuid4
from statistics import mean
from sqlalchemy import desc,select
from sqlalchemy.orm import Session
from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.advanced_trade_builder.contracts import TradeLeg,LegSide,OptionRight
from trading_ai.advanced_trade_builder.service import AdvancedTradeBuilderService
from trading_ai.execution_workspace.models import ExecutionIntentModel
from trading_ai.institutional_options.models import InstitutionalDecisionSnapshotModel
from trading_ai.option_valuation_intelligence.models import OptionValuationSnapshotModel
from trading_ai.broker.ibkr.database_models import BrokerOrderModel,BrokerExecutionModel
from .models import (
    ExecutionIntelligenceSnapshotModel,ExecutionIntelligenceEventModel,
    ExecutionOrderTelemetryModel,ExecutionFillEventModel,WorkingOrderAssessmentModel,
    ExecutionLearningSampleModel,
)
from .policy import load_execution_intelligence_policy
from .provider import PolygonDirectExecutionQuoteProvider,ExecutionQuoteError

def now(): return datetime.now(timezone.utc).isoformat()
def _dt(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except Exception:return None
def _age(ts,reference=None):
    d=_dt(ts)
    if not d:return None
    return max(0.0,((reference or datetime.now(timezone.utc))-d).total_seconds())
def _pct_change(new,old):
    return (float(new)-float(old))/max(abs(float(old)),1e-9)*100.0

class ExecutionIntelligenceService:
    WORKING_STATES={'SUBMITTED','ACKNOWLEDGED','PARTIALLY_FILLED'}
    def __init__(self,s:Session,provider=None): self.s=s;self.provider=provider

    @staticmethod
    def package_price(legs,price_key='limit_price'):
        from math import gcd
        qs=[max(1,int(round(float(x.get('quantity',1))))) for x in legs];base=qs[0]
        for q in qs[1:]:base=gcd(base,q)
        total=0.0
        for x in legs:
            ratio=float(x.get('quantity',1))/max(base,1);sign=1 if str(x.get('side')).upper()=='BUY' else -1
            total+=sign*ratio*float(x.get(price_key,0) or 0)
        return round(total,4)

    def _approval_envelope(self,m,policy):
        meta=dict(m.metadata_json or {});existing=dict(meta.get('execution_approval_envelope') or {})
        if existing:return existing
        reference=self.package_price(list(m.legs_json));drift=policy.max_price_drift_pct/100.0
        return {'reference_price':reference,'max_adverse_drift_pct':policy.max_price_drift_pct,'maximum_debit':round(reference*(1+drift),4) if reference>=0 else None,'minimum_credit':round(abs(reference)*(1-drift),4) if reference<0 else None,'approved_max_loss':float(m.max_loss),'created_at':now(),'policy_version':policy.policy_version}

    def _upstream_metrics(self,m):
        recommendation_id=str((m.metadata_json or {}).get('m62_lineage',{}).get('contract_recommendation_id') or '')
        valuation=self.s.scalar(select(OptionValuationSnapshotModel).where(OptionValuationSnapshotModel.contract_recommendation_id==recommendation_id).order_by(desc(OptionValuationSnapshotModel.snapshot_timestamp)).limit(1)) if recommendation_id else None
        val_payload=dict(valuation.payload_json or {}) if valuation else {}
        edge=float(getattr(valuation,'edge_score',0) or val_payload.get('edge_score') or 0)
        decision_id=(m.metadata_json or {}).get('decision_snapshot_id');decision=self.s.get(InstitutionalDecisionSnapshotModel,decision_id) if decision_id else None;dp=dict(decision.payload_json or {}) if decision else {}
        ev=float(getattr(decision,'expected_value',0) or dp.get('expected_value') or 0);ror=float(dp.get('expected_return_on_risk') or dp.get('selected_strategy_metrics',{}).get('expected_return_on_risk') or 0)
        return edge,ev,ror

    def _evaluate(self,m,tp,policy,provider,actor,reason,purpose):
        envelope=self._approval_envelope(m,policy);samples=[]
        for sample_index in range(policy.quote_stability_samples):
            quote_map={};underlying=None
            for leg in list(m.legs_json):
                sym=str(leg.get('option_symbol') or '').strip()
                if not sym:raise ValueError('Exact Polygon option_symbol is required for execution-time quoting')
                q=provider.option_quote(m.symbol,sym);quote_map[sym]=q.to_dict();underlying=underlying or q.underlying_price
            try:
                u=provider.underlying_quote(m.symbol);underlying=u.midpoint or u.last or underlying;underlying_quote=u.to_dict()
            except Exception as e:underlying_quote={'instrument':m.symbol,'error':str(e),'fallback_underlying_price':underlying}
            samples.append({'sample':sample_index+1,'quotes':quote_map,'underlying_quote':underlying_quote,'underlying_price':underlying,'captured_at':now()})
            if sample_index+1<policy.quote_stability_samples and policy.quote_stability_interval_ms:sleep(policy.quote_stability_interval_ms/1000.0)

        latest=samples[-1];live_legs=[];ages=[];spreads=[];mid_series={}
        for leg in list(m.legs_json):
            sym=str(leg['option_symbol']);q=latest['quotes'][sym];bid=float(q.get('bid') or 0);ask=float(q.get('ask') or 0);mid=float(q.get('midpoint') or 0);last=float(q.get('last') or 0)
            side=str(leg.get('side')).upper();exec_px=(ask if side=='BUY' and ask>0 else bid if side=='SELL' and bid>0 else mid or last);mid_px=mid or last or exec_px
            if exec_px<=0:raise ExecutionQuoteError(f'No executable Polygon price for {sym}')
            spread=(ask-bid)/mid*100 if bid>0 and ask>=bid and mid>0 else 100.0;spreads.append(spread);age=_age(q.get('quote_timestamp'));ages.append(age)
            mid_series[sym]=[float(x['quotes'][sym].get('midpoint') or x['quotes'][sym].get('last') or 0) for x in samples]
            live_legs.append({**leg,'execution_price':exec_px,'midpoint_price':mid_px,'fresh_bid':bid,'fresh_ask':ask,'fresh_midpoint':mid,'fresh_spread_pct':spread,'quote_timestamp':q.get('quote_timestamp'),'quote_age_seconds':age})

        fresh_exec=self.package_price([{**x,'limit_price':x['execution_price']} for x in live_legs])
        fresh_mid=self.package_price([{**x,'limit_price':x['midpoint_price']} for x in live_legs])
        approved=float(envelope['reference_price']);market_drift=_pct_change(fresh_mid,approved)
        crossing_slippage=_pct_change(fresh_exec,fresh_mid) if abs(fresh_mid)>1e-9 else 0.0
        stability_moves=[]
        for vals in mid_series.values():
            vals=[x for x in vals if x>0]
            if vals:stability_moves.append((max(vals)-min(vals))/max(mean(vals),1e-9)*100)
        max_move=max(stability_moves or [0.0]);stability_score=max(0.0,100.0-max_move*20.0)
        timestamps_present=bool(ages) and all(x is not None for x in ages);valid_ages=[x for x in ages if x is not None];max_age=max(valid_ages) if valid_ages else None;max_spread=max(spreads or [100.0])
        age_penalty=0 if max_age is None else min(25.0,max_age/max(policy.max_quote_age_seconds,1e-9)*10.0)
        spread_penalty=min(25.0,max_spread/max(policy.maximum_spread_pct,1e-9)*10.0) if policy.maximum_spread_pct>0 else 0
        confidence=max(0.0,min(100.0,stability_score-age_penalty-spread_penalty))
        aggression=max(0.0,min(1.0,policy.initial_limit_aggression_pct/100.0))
        governed=round(fresh_mid+aggression*(fresh_exec-fresh_mid),4)
        if approved>=0 and envelope.get('maximum_debit') is not None: governed=min(governed,float(envelope['maximum_debit']))
        if approved<0 and envelope.get('minimum_credit') is not None: governed=min(governed,-float(envelope['minimum_credit']))

        trade_legs=tuple(TradeLeg(side=LegSide(str(x['side']).upper()),quantity=int(x['quantity']),option_right=OptionRight(str(x['option_right']).upper()),strike=float(x['strike']),expiry=str(x['expiry']),limit_price=float(x['midpoint_price']),delta=x.get('delta'),gamma=x.get('gamma'),theta=x.get('theta'),vega=x.get('vega'),option_symbol=str(x['option_symbol'])) for x in live_legs)
        debit,credit,max_loss,max_profit,rr,budget,greeks,econ_checks=AdvancedTradeBuilderService.economics(trade_legs,float(tp.capital),float(tp.risk_budget_pct))
        edge,ev,ror=self._upstream_metrics(m)
        checks={
            'direct_polygon_quotes':True,'quote_timestamp_present':timestamps_present,
            'quote_fresh':bool(timestamps_present and max_age is not None and max_age<=policy.max_quote_age_seconds),
            'price_drift_within_envelope':market_drift<=policy.max_price_drift_pct,
            'risk_within_budget':bool(econ_checks.get('risk_within_budget')),'defined_risk':bool(econ_checks.get('defined_risk')),
            'spread_within_policy':max_spread<=policy.maximum_spread_pct,'execution_confidence':confidence>=policy.minimum_execution_confidence,
            'edge_threshold':edge>=policy.minimum_edge_score,'expected_value_threshold':ev>=policy.minimum_expected_value,'return_on_risk_threshold':ror>=policy.minimum_return_on_risk,
        }
        valid=all(checks.values())
        if not checks['direct_polygon_quotes'] or not checks['quote_timestamp_present'] or not checks['quote_fresh']:decision='BLOCK'
        elif not checks['risk_within_budget'] or not checks['defined_risk'] or not checks['price_drift_within_envelope']:decision='REVALIDATE'
        elif not checks['execution_confidence'] or not checks['spread_within_policy']:decision='WAIT'
        else:decision='EXECUTE'
        evidence={'purpose':purpose,'fresh_debit':debit,'fresh_credit':credit,'fresh_max_profit':max_profit,'reward_risk_ratio':rr,'fresh_greeks':greeks,'upstream_edge_score':edge,'upstream_expected_value':ev,'upstream_return_on_risk':ror,'stability_max_midpoint_move_pct':max_move,'maximum_spread_pct':max_spread,'underlying_price':latest.get('underlying_price'),'quote_timestamp_status':'PRESENT' if timestamps_present else 'MISSING','fresh_midpoint_price':fresh_mid,'fresh_executable_price':fresh_exec,'market_drift_pct':market_drift,'crossing_slippage_pct':crossing_slippage,'limit_aggression_pct':policy.initial_limit_aggression_pct}
        sid=f'M70-EXEC-{uuid4().hex.upper()}';created=now()
        snap=ExecutionIntelligenceSnapshotModel(execution_snapshot_id=sid,execution_intent_id=m.execution_intent_id,execution_intent_version=m.version,trade_plan_id=m.trade_plan_id,symbol=m.symbol,strategy=m.strategy,decision=decision,execution_confidence=round(confidence,4),approved_reference_price=approved,fresh_executable_price=fresh_exec,governed_limit_price=governed,adverse_price_drift_pct=round(market_drift,6),quote_age_seconds=round(max_age,6) if max_age is not None else None,fresh_max_loss=float(max_loss),risk_budget_amount=float(budget),validation_json={'valid':valid,'checks':checks},quotes_json={'samples':samples,'live_legs':live_legs},envelope_json=envelope,policy_json=policy.as_dict(),evidence_json=evidence,created_at=created)
        self.s.add(snap);self.s.add(ExecutionIntelligenceEventModel(event_id=f'M70-EVT-{uuid4().hex.upper()}',execution_snapshot_id=sid,execution_intent_id=m.execution_intent_id,event_type=f'EXECUTION_{decision}',actor=actor,reason=reason,payload_json={'validation':snap.validation_json,'evidence':evidence},created_at=created));self.s.commit()
        return snap

    def preflight(self,intent_id,actor='SYSTEM',reason='Execution-time preflight'):
        m=self.s.get(ExecutionIntentModel,intent_id)
        if not m:raise KeyError('Execution intent not found')
        if m.state!='APPROVED':raise ValueError('Execution intent must be APPROVED for execution-time revalidation')
        tp=self.s.get(TradePlanModel,m.trade_plan_id)
        if not tp:raise KeyError('Trade plan not found')
        policy=load_execution_intelligence_policy()
        if not policy.direct_polygon_enabled:raise ValueError('Direct Polygon execution quote policy is disabled; execution fails closed')
        snap=self._evaluate(m,tp,policy,self.provider or PolygonDirectExecutionQuoteProvider(),actor,reason,'PRE_ROUTE')
        return self.to_dict(snap)

    def assess_working(self,intent_id,actor='SYSTEM',reason='Working-order assessment'):
        m=self.s.get(ExecutionIntentModel,intent_id)
        if not m:raise KeyError('Execution intent not found')
        if m.state not in self.WORKING_STATES:raise ValueError('Execution intent must be working or partially filled')
        tp=self.s.get(TradePlanModel,m.trade_plan_id)
        if not tp:raise KeyError('Trade plan not found')
        policy=load_execution_intelligence_policy();snap=self._evaluate(m,tp,policy,self.provider or PolygonDirectExecutionQuoteProvider(),actor,reason,'WORKING_ORDER')
        aggregate=str((m.broker_json or {}).get('aggregate_id') or '');broker=self.s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.aggregate_id==aggregate)) if aggregate else None
        current=float(broker.limit_price if broker and broker.limit_price is not None else self.package_price(list(m.legs_json)))
        age=_age(broker.submitted_at) if broker else 0.0;filled=float(broker.filled_quantity or 0) if broker else 0.0;remaining=float(broker.remaining_quantity or 0) if broker else 0.0
        checks=dict(snap.validation_json.get('checks') or {});reprice_count=int(((broker.raw_json or {}) if broker else {}).get('m70_reprice_count',0) or 0)
        delta_pct=abs(_pct_change(float(snap.governed_limit_price),current)) if abs(current)>1e-9 else 0.0
        if snap.decision in {'BLOCK','REVALIDATE'} or age>policy.working_order_max_age_seconds:action='CANCEL'
        elif snap.decision=='WAIT':action='CONTINUE'
        elif reprice_count<policy.maximum_reprices and age>=policy.working_reprice_after_seconds and delta_pct>=policy.working_reprice_min_change_pct:action='REPRICE'
        else:action='CONTINUE'
        aid=f'M70-WORK-{uuid4().hex.upper()}';evidence={'decision':snap.decision,'checks':checks,'reprice_count':reprice_count,'maximum_reprices':policy.maximum_reprices,'limit_change_pct':delta_pct,'market_drift_pct':snap.adverse_price_drift_pct,'crossing_slippage_pct':snap.evidence_json.get('crossing_slippage_pct'),'quote_age_seconds':snap.quote_age_seconds}
        row=WorkingOrderAssessmentModel(assessment_id=aid,execution_intent_id=m.execution_intent_id,execution_snapshot_id=snap.execution_snapshot_id,state=m.state,recommended_action=action,current_limit_price=current,governed_limit_price=float(snap.governed_limit_price),filled_quantity=filled,remaining_quantity=remaining,working_age_seconds=float(age or 0),evidence_json=evidence,created_at=now());self.s.add(row);self.s.commit()
        return {'assessment_id':aid,'execution_intent_id':m.execution_intent_id,'execution_snapshot_id':snap.execution_snapshot_id,'state':m.state,'recommended_action':action,'current_limit_price':current,'governed_limit_price':float(snap.governed_limit_price),'filled_quantity':filled,'remaining_quantity':remaining,'working_age_seconds':float(age or 0),'evidence':evidence,'snapshot':self.to_dict(snap)}

    def record_submission(self,m,snapshot:dict,broker_result:dict,submitted_limit:float):
        row=self.s.get(ExecutionOrderTelemetryModel,m.execution_intent_id);ts=now();ev=dict(snapshot.get('evidence_json') or {})
        if row is None:
            row=ExecutionOrderTelemetryModel(execution_intent_id=m.execution_intent_id,trade_plan_id=m.trade_plan_id,execution_snapshot_id=snapshot.get('execution_snapshot_id'),aggregate_id=(m.broker_json or {}).get('aggregate_id'),broker_order_id=broker_result.get('broker_order_id'),symbol=m.symbol,strategy=m.strategy,state=str(broker_result.get('status') or 'SUBMITTED'),approved_reference_price=float(snapshot.get('approved_reference_price') or 0),fresh_midpoint_price=float(ev.get('fresh_midpoint_price') or 0),fresh_executable_price=float(snapshot.get('fresh_executable_price') or 0),submitted_limit_price=float(submitted_limit),average_fill_price=None,filled_quantity=float(broker_result.get('filled_quantity') or 0),remaining_quantity=float(broker_result.get('remaining_quantity') or 0),commission_total=0,quote_age_seconds=snapshot.get('quote_age_seconds'),execution_confidence=float(snapshot.get('execution_confidence') or 0),market_drift_pct=float(snapshot.get('adverse_price_drift_pct') or 0),execution_slippage_pct=float(ev.get('crossing_slippage_pct') or 0),realized_slippage_pct=None,fill_rate_pct=0,execution_quality_score=float(snapshot.get('execution_confidence') or 0),first_submitted_at=ts,acknowledged_at=ts if str(broker_result.get('status') or '').upper() in {'PRESUBMITTED','SUBMITTED','ACKNOWLEDGED','WORKING'} else None,first_fill_at=None,filled_at=None,updated_at=ts,details_json={'submission':broker_result,'preflight':snapshot});self.s.add(row)
        else:
            row.execution_snapshot_id=snapshot.get('execution_snapshot_id');row.broker_order_id=broker_result.get('broker_order_id');row.submitted_limit_price=float(submitted_limit);row.state=str(broker_result.get('status') or row.state);row.updated_at=ts;row.details_json={**dict(row.details_json or {}),'submission':broker_result,'preflight':snapshot}
        self.s.commit()

    def record_broker_sync(self,m,broker:BrokerOrderModel|None):
        if not broker:return
        row=self.s.get(ExecutionOrderTelemetryModel,m.execution_intent_id);ts=now()
        if row is None:
            row=ExecutionOrderTelemetryModel(execution_intent_id=m.execution_intent_id,trade_plan_id=m.trade_plan_id,execution_snapshot_id=None,aggregate_id=broker.aggregate_id,broker_order_id=broker.broker_order_id,symbol=m.symbol,strategy=m.strategy,state=broker.status,approved_reference_price=0,fresh_midpoint_price=0,fresh_executable_price=0,submitted_limit_price=float(broker.limit_price or 0),average_fill_price=None,filled_quantity=0,remaining_quantity=float(broker.quantity or 0),commission_total=0,quote_age_seconds=None,execution_confidence=0,market_drift_pct=0,execution_slippage_pct=0,realized_slippage_pct=None,fill_rate_pct=0,execution_quality_score=0,first_submitted_at=broker.submitted_at,acknowledged_at=None,first_fill_at=None,filled_at=None,updated_at=ts,details_json={});self.s.add(row)
        row.state=broker.status;row.broker_order_id=broker.broker_order_id;row.average_fill_price=float(broker.average_fill_price or 0) or None;row.filled_quantity=float(broker.filled_quantity or 0);row.remaining_quantity=float(broker.remaining_quantity or 0);row.fill_rate_pct=round(row.filled_quantity/max(float(broker.quantity or 1),1e-9)*100,4);row.updated_at=ts
        if row.filled_quantity>0 and not row.first_fill_at:row.first_fill_at=broker.updated_at
        if str(broker.status).upper()=='FILLED':row.filled_at=broker.updated_at
        executions=list(self.s.scalars(select(BrokerExecutionModel).where(BrokerExecutionModel.aggregate_id==broker.aggregate_id)))
        for ex in executions:
            fid=f'M70-FILL-{ex.execution_id}'
            if self.s.get(ExecutionFillEventModel,fid) is None:self.s.add(ExecutionFillEventModel(fill_event_id=fid,execution_intent_id=m.execution_intent_id,aggregate_id=broker.aggregate_id,broker_execution_id=ex.execution_id,broker_order_id=ex.broker_order_id,symbol=ex.symbol,side=ex.side,quantity=float(ex.quantity),price=float(ex.price),commission=float(ex.commission or 0),executed_at=ex.executed_at,payload_json=dict(ex.raw_json or {})))
        row.commission_total=round(sum(float(x.commission or 0) for x in executions),4)
        if row.average_fill_price is not None and abs(row.submitted_limit_price)>1e-9:row.realized_slippage_pct=round(_pct_change(row.average_fill_price,row.submitted_limit_price),6)
        quality=float(row.execution_confidence);quality-=min(30,abs(float(row.realized_slippage_pct or 0))*6);quality-=min(15,float(row.quote_age_seconds or 0)/max(load_execution_intelligence_policy().max_quote_age_seconds,1e-9)*5);row.execution_quality_score=round(max(0,min(100,quality)),4)
        if str(broker.status).upper() in {'FILLED','CANCELLED','CANCELED','REJECTED','INACTIVE'}:
            outcome='FILLED' if str(broker.status).upper()=='FILLED' else str(broker.status).upper();sample=self.s.get(ExecutionLearningSampleModel,m.execution_intent_id)
            features={'execution_confidence':row.execution_confidence,'quote_age_seconds':row.quote_age_seconds,'market_drift_pct':row.market_drift_pct,'execution_slippage_pct':row.execution_slippage_pct,'strategy':row.strategy}
            outcomes={'outcome':outcome,'fill_rate_pct':row.fill_rate_pct,'realized_slippage_pct':row.realized_slippage_pct,'commission_total':row.commission_total,'average_fill_price':row.average_fill_price}
            if sample is None:self.s.add(ExecutionLearningSampleModel(execution_intent_id=m.execution_intent_id,symbol=m.symbol,strategy=m.strategy,outcome=outcome,execution_quality_score=row.execution_quality_score,features_json=features,outcome_json=outcomes,created_at=ts,updated_at=ts))
            else:sample.outcome=outcome;sample.execution_quality_score=row.execution_quality_score;sample.features_json=features;sample.outcome_json=outcomes;sample.updated_at=ts
        self.s.commit()

    def latest(self,intent_id):
        row=self.s.scalar(select(ExecutionIntelligenceSnapshotModel).where(ExecutionIntelligenceSnapshotModel.execution_intent_id==intent_id).order_by(desc(ExecutionIntelligenceSnapshotModel.created_at)).limit(1));return self.to_dict(row) if row else None

    def dashboard(self,limit=200):
        snaps=list(self.s.scalars(select(ExecutionIntelligenceSnapshotModel).order_by(desc(ExecutionIntelligenceSnapshotModel.created_at)).limit(limit)))
        orders=list(self.s.scalars(select(ExecutionOrderTelemetryModel).order_by(desc(ExecutionOrderTelemetryModel.updated_at)).limit(limit)))
        fills=list(self.s.scalars(select(ExecutionFillEventModel).order_by(desc(ExecutionFillEventModel.executed_at)).limit(limit)))
        working=list(self.s.scalars(select(WorkingOrderAssessmentModel).order_by(desc(WorkingOrderAssessmentModel.created_at)).limit(limit)))
        filled=[x for x in orders if x.average_fill_price is not None]
        return {'count':len(snaps),'execute':sum(x.decision=='EXECUTE' for x in snaps),'wait':sum(x.decision=='WAIT' for x in snaps),'revalidate':sum(x.decision=='REVALIDATE' for x in snaps),'blocked':sum(x.decision=='BLOCK' for x in snaps),'average_confidence':round(mean([x.execution_confidence for x in snaps]),2) if snaps else 0,'average_quote_age_seconds':round(mean([x.quote_age_seconds for x in snaps if x.quote_age_seconds is not None]),3) if any(x.quote_age_seconds is not None for x in snaps) else 0,'average_market_drift_pct':round(mean([x.adverse_price_drift_pct for x in snaps]),3) if snaps else 0,'average_execution_quality':round(mean([x.execution_quality_score for x in orders]),2) if orders else 0,'average_realized_slippage_pct':round(mean([x.realized_slippage_pct for x in filled if x.realized_slippage_pct is not None]),4) if any(x.realized_slippage_pct is not None for x in filled) else 0,'fill_rate_pct':round(sum(1 for x in orders if x.state.upper()=='FILLED')/len(orders)*100,2) if orders else 0,'snapshots':[self.to_dict(x) for x in snaps],'orders':[self.telemetry_dict(x) for x in orders],'fills':[self.fill_dict(x) for x in fills],'working_assessments':[self.working_dict(x) for x in working]}

    @staticmethod
    def to_dict(x):
        if not x:return None
        return {k:getattr(x,k) for k in ('execution_snapshot_id','execution_intent_id','execution_intent_version','trade_plan_id','symbol','strategy','decision','execution_confidence','approved_reference_price','fresh_executable_price','governed_limit_price','adverse_price_drift_pct','quote_age_seconds','fresh_max_loss','risk_budget_amount','validation_json','quotes_json','envelope_json','policy_json','evidence_json','created_at')}
    @staticmethod
    def telemetry_dict(x):
        return {k:getattr(x,k) for k in ('execution_intent_id','trade_plan_id','execution_snapshot_id','aggregate_id','broker_order_id','symbol','strategy','state','approved_reference_price','fresh_midpoint_price','fresh_executable_price','submitted_limit_price','average_fill_price','filled_quantity','remaining_quantity','commission_total','quote_age_seconds','execution_confidence','market_drift_pct','execution_slippage_pct','realized_slippage_pct','fill_rate_pct','execution_quality_score','first_submitted_at','acknowledged_at','first_fill_at','filled_at','updated_at','details_json')}
    @staticmethod
    def fill_dict(x):return {k:getattr(x,k) for k in ('fill_event_id','execution_intent_id','aggregate_id','broker_execution_id','broker_order_id','symbol','side','quantity','price','commission','executed_at','payload_json')}
    @staticmethod
    def working_dict(x):return {k:getattr(x,k) for k in ('assessment_id','execution_intent_id','execution_snapshot_id','state','recommended_action','current_limit_price','governed_limit_price','filled_quantity','remaining_quantity','working_age_seconds','evidence_json','created_at')}
