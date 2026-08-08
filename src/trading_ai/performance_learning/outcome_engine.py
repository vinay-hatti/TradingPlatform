from __future__ import annotations
from datetime import datetime, timezone
from math import log, sqrt
from statistics import mean, pstdev
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from trading_ai.portfolio_intelligence.models import ManagedPositionModel, PositionEventModel
from trading_ai.institutional_options.models import InstitutionalDecisionSnapshotModel
from trading_ai.portfolio_risk_allocation.models import PortfolioDecisionIntelligenceModel
from trading_ai.broker.ibkr.database_models import BrokerOrderModel, BrokerExecutionModel
from .models import (TradeOutcomeModel,PerformanceAttributionSnapshotModel,ProbabilityCalibrationSnapshotModel,CounterfactualOutcomeModel,PerformanceLearningPublicationModel,PerformanceLearningReportModel)
from .service import PerformanceLearningService, now, clamp

POLICY_VERSION='M65-PERFORMANCE-LEARNING-1.0'

def _id(prefix:str)->str:return f'{prefix}-{uuid4().hex.upper()}'
def _days(a:str|None,b:str|None)->float:
 try:return max(0.0,(datetime.fromisoformat((b or now()).replace('Z','+00:00'))-datetime.fromisoformat((a or now()).replace('Z','+00:00'))).total_seconds()/86400)
 except Exception:return 0.0

def _metric(rows,key):
 vals=[float(r.get(key,0) or 0) for r in rows]
 return round(mean(vals),6) if vals else 0.0

class Milestone65LearningService:
 def __init__(self,session:Session):self.s=session
 def reconstruct_outcomes(self,portfolio_id='PAPER-PRIMARY'):
  positions=list(self.s.scalars(select(ManagedPositionModel).where(ManagedPositionModel.portfolio_id==portfolio_id)))
  created=refreshed=0
  for p in positions:
   decision=self.s.scalar(select(InstitutionalDecisionSnapshotModel).where(InstitutionalDecisionSnapshotModel.opportunity_id==p.opportunity_id))
   pd=self.s.scalar(select(PortfolioDecisionIntelligenceModel).where(PortfolioDecisionIntelligenceModel.opportunity_id==p.opportunity_id).order_by(PortfolioDecisionIntelligenceModel.created_at.desc()).limit(1))
   existing=self.s.scalar(select(TradeOutcomeModel).where(TradeOutcomeModel.position_id==p.position_id,TradeOutcomeModel.position_version==p.version))
   mark=p.mark_json or {};meta=p.metadata_json or {};health=p.health_json or {};dp=(decision.payload_json if decision else {}) or {}
   entry=max(float(p.entry_value or 0),1e-9);realized=float(p.realized_pnl or 0);unrealized=float(mark.get('unrealized_pnl',0) or 0);pnl=realized+(0 if p.state=='CLOSED' else unrealized)
   ret=float(meta.get('realized_return_pct',mark.get('unrealized_return_pct',pnl/entry*100)))
   prob=clamp((decision.calibrated_probability if decision and decision.calibrated_probability is not None else meta.get('predicted_probability',health.get('confidence',.5))))
   expected=float(decision.expected_value if decision and decision.expected_value is not None else dp.get('valuation',{}).get('expected_value',0) or 0)
   events=list(self.s.scalars(select(PositionEventModel).where(PositionEventModel.position_id==p.position_id)))
   drawdowns=[float((e.payload_json or {}).get('drawdown_pct',0) or 0) for e in events]
   payload={'state':p.state,'symbol':p.symbol,'direction':p.direction,'trade_plan_id':p.trade_plan_id,'execution_id':p.execution_id,'decision_state_hash':decision.state_hash if decision else None,'portfolio_fit_score':pd.portfolio_fit_score if pd else None,'opportunity_cost_score':pd.opportunity_cost_score if pd else None,'recommended_quantity':pd.recommended_quantity if pd else None,'actual_quantity':meta.get('quantity',1),'market_regime':dp.get('underlying_thesis',{}).get('market_regime','UNKNOWN'),'exit_reason':meta.get('exit_reason',p.decision_json.get('reason')),'management_mode':meta.get('automation_mode','UNKNOWN'),'event_count':len(events),'option_valuation_intelligence':dp.get('option_valuation_intelligence',{}),'valuation_edge_pct':(dp.get('option_valuation_intelligence',{}) or {}).get('mispricing_pct'),'relative_value_edge_pct':((dp.get('option_valuation_intelligence',{}) or {}).get('components') or {}).get('relative_value_edge_pct'),'event_edge_pct':((dp.get('option_valuation_intelligence',{}) or {}).get('components') or {}).get('event_edge_pct')}
   values=dict(position_id=p.position_id,position_version=p.version,portfolio_id=portfolio_id,opportunity_id=p.opportunity_id,decision_snapshot_id=decision.decision_snapshot_id if decision else None,portfolio_decision_id=pd.decision_intelligence_id if pd else None,strategy=p.strategy,market_regime=payload['market_regime'],outcome='WIN' if ret>0 else 'LOSS' if ret<0 else 'OPEN' if p.state!='CLOSED' else 'FLAT',predicted_probability=prob,expected_value=expected,realized_pnl=pnl,realized_return_pct=ret,maximum_drawdown_pct=abs(min(drawdowns+[0])),holding_days=_days(p.opened_at,p.closed_at),opened_at=p.opened_at,closed_at=p.closed_at,reconstructed_at=now(),payload_json=payload)
   if existing:
    for k,v in values.items():setattr(existing,k,v)
    refreshed+=1
   else:
    self.s.add(TradeOutcomeModel(outcome_id=_id('M65-OUT'),**values));created+=1
  self.s.commit();return {'requested':len(positions),'created':created,'refreshed':refreshed}
 def _rows(self,portfolio_id,closed_only=True):
  q=select(TradeOutcomeModel).where(TradeOutcomeModel.portfolio_id==portfolio_id)
  rows=list(self.s.scalars(q));return [self._dto(x) for x in rows if not closed_only or x.closed_at or x.outcome in ('WIN','LOSS','FLAT')]
 @staticmethod
 def _dto(x):
  return {'outcome_id':x.outcome_id,'position_id':x.position_id,'opportunity_id':x.opportunity_id,'strategy':x.strategy,'market_regime':x.market_regime,'predicted_probability':x.predicted_probability,'expected_value':x.expected_value,'realized_pnl':x.realized_pnl,'realized_return_pct':x.realized_return_pct,'maximum_drawdown_pct':x.maximum_drawdown_pct,'holding_days':x.holding_days,'outcome':x.outcome,**(x.payload_json or {})}
 @staticmethod
 def calibration_metrics(rows):
  eligible=[r for r in rows if r['outcome'] in ('WIN','LOSS','FLAT')]
  if not eligible:return {'sample_size':0,'brier_score':0.0,'log_loss':0.0,'expected_calibration_error':0.0,'buckets':[]}
  bs=[];ll=[]
  for r in eligible:
   p=min(.999999,max(.000001,float(r['predicted_probability'])));y=1 if r['realized_return_pct']>0 else 0;bs.append((p-y)**2);ll.append(-(y*log(p)+(1-y)*log(1-p)))
  buckets=[b.to_dict() for b in PerformanceLearningService.calibration(eligible)];ece=sum(b['calibration_error']*b['count'] for b in buckets)/len(eligible) if buckets else 0
  return {'sample_size':len(eligible),'brier_score':round(mean(bs),6),'log_loss':round(mean(ll),6),'expected_calibration_error':round(ece,6),'buckets':buckets}
 def _attribution(self,rows):
  dimensions=('strategy','market_regime','symbol','direction','management_mode')
  out={}
  for dim in dimensions:
   groups={}
   for r in rows:groups.setdefault(str(r.get(dim,'UNKNOWN')),[]).append(r)
   out[dim]={k:{'sample_size':len(v),'win_rate':round(sum(1 for x in v if x['realized_return_pct']>0)/len(v)*100,2),'expectancy_pct':_metric(v,'realized_return_pct'),'realized_pnl':round(sum(x['realized_pnl'] for x in v),2),'average_holding_days':_metric(v,'holding_days')} for k,v in groups.items()}
  return out
 def _execution(self,portfolio_id):
  orders=list(self.s.scalars(select(BrokerOrderModel).where(BrokerOrderModel.portfolio_id==portfolio_id)))
  executions=list(self.s.scalars(select(BrokerExecutionModel).where(BrokerExecutionModel.portfolio_id==portfolio_id)))
  costs=[];times=[]
  for o in orders:
   if o.average_fill_price and o.limit_price is not None:costs.append((o.average_fill_price-o.limit_price)*(1 if o.side.upper()=='BUY' else -1))
   times.append(_days(o.submitted_at,o.updated_at)*86400)
  return {'orders':len(orders),'executions':len(executions),'average_slippage':round(mean(costs),6) if costs else 0.0,'total_commission':round(sum(e.commission for e in executions),2),'average_time_to_fill_seconds':round(mean(times),2) if times else 0.0,'fill_rate_pct':round(sum(1 for o in orders if o.filled_quantity>0)/max(len(orders),1)*100,2)}
 def _management(self,rows):
  return {'sample_size':len(rows),'average_drawdown_pct':_metric(rows,'maximum_drawdown_pct'),'average_holding_days':_metric(rows,'holding_days'),'average_return_pct':_metric(rows,'realized_return_pct'),'by_mode':self._attribution(rows).get('management_mode',{})}
 def _portfolio_learning(self,rows):
  governed=[r for r in rows if r.get('portfolio_fit_score') is not None]
  return {'sample_size':len(governed),'average_portfolio_fit':_metric(governed,'portfolio_fit_score'),'average_opportunity_cost':_metric(governed,'opportunity_cost_score'),'recommended_size_alignment_pct':round(sum(1 for r in governed if float(r.get('actual_quantity',1) or 1)==float(r.get('recommended_quantity',1) or 1))/max(len(governed),1)*100,2),'high_fit_expectancy_pct':_metric([r for r in governed if float(r.get('portfolio_fit_score',0))>=75],'realized_return_pct'),'low_fit_expectancy_pct':_metric([r for r in governed if float(r.get('portfolio_fit_score',0))<75],'realized_return_pct')}
 def evaluate_counterfactuals(self,portfolio_id='PAPER-PRIMARY'):
  decisions=list(self.s.scalars(select(PortfolioDecisionIntelligenceModel).where(PortfolioDecisionIntelligenceModel.portfolio_id==portfolio_id)))
  outcomes={x.opportunity_id:x for x in self.s.scalars(select(TradeOutcomeModel).where(TradeOutcomeModel.portfolio_id==portfolio_id))}
  created=refreshed=0
  for d in decisions:
   existing=self.s.scalar(select(CounterfactualOutcomeModel).where(CounterfactualOutcomeModel.portfolio_id==portfolio_id,CounterfactualOutcomeModel.opportunity_id==d.opportunity_id,CounterfactualOutcomeModel.decision_state_hash==d.state_hash))
   o=outcomes.get(d.opportunity_id);selected=o is not None;observed=o.realized_return_pct if o else None;status='OBSERVED' if o else 'PENDING_MARKOUT'
   payload={'rank':d.rank,'final_portfolio_score':d.final_portfolio_score,'portfolio_fit_score':d.portfolio_fit_score,'opportunity_cost_score':d.opportunity_cost_score,'recommended_quantity':d.recommended_quantity,'counterfactual_type':'EXECUTED' if selected else 'NOT_EXECUTED'}
   vals=dict(portfolio_id=portfolio_id,opportunity_id=d.opportunity_id,decision_state_hash=d.state_hash,decision=d.decision,selected=1 if selected else 0,predicted_probability=float((d.payload_json or {}).get('calibrated_probability',.5) or .5),observed_return_pct=observed,evaluation_status=status,evaluated_at=now(),payload_json=payload)
   if existing:
    for k,v in vals.items():setattr(existing,k,v)
    refreshed+=1
   else:self.s.add(CounterfactualOutcomeModel(counterfactual_id=_id('M65-CF'),**vals));created+=1
  self.s.commit();return {'requested':len(decisions),'created':created,'refreshed':refreshed}
 def build_command_center(self,portfolio_id='PAPER-PRIMARY',actor='m65-engine'):
  self.reconstruct_outcomes(portfolio_id);self.evaluate_counterfactuals(portfolio_id)
  rows=self._rows(portfolio_id,closed_only=False);closed=[r for r in rows if r['outcome'] in ('WIN','LOSS','FLAT')]
  base=PerformanceLearningService.build_report(closed,portfolio_id,_id('M65-REPORT')).to_dict();cal=self.calibration_metrics(closed);attr=self._attribution(closed);execution=self._execution(portfolio_id);management=self._management(closed);portfolio=self._portfolio_learning(closed)
  returns=[r['realized_return_pct'] for r in closed];avg=mean(returns) if returns else 0;sd=pstdev(returns) if len(returns)>1 else 0;down=pstdev([min(0,r) for r in returns]) if len(returns)>1 else 0
  command={'policy_version':POLICY_VERSION,'sample_governance':{'minimum_for_recommendation':10,'minimum_for_activation':30,'automatic_activation':False},'overall':base['overall'],'attribution':attr,'calibration_metrics':cal,'execution_quality':execution,'management_effectiveness':management,'portfolio_allocation_learning':portfolio,'risk_adjusted':{'sharpe_proxy':round(avg/sd*sqrt(252),4) if sd else 0.0,'sortino_proxy':round(avg/down*sqrt(252),4) if down else 0.0},'model_drift':{'status':'INSUFFICIENT_SAMPLE' if len(closed)<30 else 'STABLE','sample_size':len(closed)},'recommendations':base['recommendations']}
  report=PerformanceLearningReportModel(report_id=base['report_id'],portfolio_id=portfolio_id,window_start=None,window_end=None,generated_at=now(),analytics_version=POLICY_VERSION,payload_json={**base,'command_center':command},generated_by=actor);self.s.add(report)
  self.s.add(PerformanceAttributionSnapshotModel(attribution_snapshot_id=_id('M65-ATTR'),portfolio_id=portfolio_id,generated_at=now(),sample_size=len(closed),payload_json=attr))
  self.s.add(ProbabilityCalibrationSnapshotModel(calibration_snapshot_id=_id('M65-CAL'),portfolio_id=portfolio_id,scope='GLOBAL',scope_value='ALL',sample_size=cal['sample_size'],brier_score=cal['brier_score'],log_loss=cal['log_loss'],expected_calibration_error=cal['expected_calibration_error'],generated_at=now(),payload_json=cal))
  pub=PerformanceLearningPublicationModel(publication_id=_id('M65-PUB'),publication_name='current_performance_learning',portfolio_id=portfolio_id,report_id=report.report_id,status='READY' if closed else 'DEGRADED',sample_size=len(closed),published_at=now(),payload_json={'report_id':report.report_id,'policy_version':POLICY_VERSION,'sample_size':len(closed),'learning_confidence':round(min(1,len(closed)/30),4),'decision_feedback':{'calibration_adjustment':round(1-cal['expected_calibration_error'],4),'execution_reliability':round(max(0,1-abs(execution['average_slippage'])/max(.01,1)),4),'management_reliability':round(min(1,len(closed)/20),4),'portfolio_reliability':round(min(1,portfolio['sample_size']/20),4)}});self.s.add(pub);self.s.commit();return {'report_id':report.report_id,'publication_id':pub.publication_id,'status':pub.status,'sample_size':len(closed),'command_center':command}
 def current_publication(self,portfolio_id='PAPER-PRIMARY'):
  p=self.s.scalar(select(PerformanceLearningPublicationModel).where(PerformanceLearningPublicationModel.portfolio_id==portfolio_id).order_by(PerformanceLearningPublicationModel.published_at.desc()).limit(1));return None if not p else {'publication_id':p.publication_id,'publication_name':p.publication_name,'status':p.status,'sample_size':p.sample_size,'published_at':p.published_at,**p.payload_json}
