from __future__ import annotations
from datetime import datetime,timezone
from statistics import mean,median
from math import prod
from uuid import uuid4
from sqlalchemy.orm import Session
from trading_ai.portfolio_intelligence.models import ManagedPositionModel,PositionAttributionModel
from .contracts import *
from .models import *
from .repository import PerformanceLearningRepository
ANALYTICS_VERSION='M58.1'
def now():return datetime.now(timezone.utc).isoformat()
def clamp(v,a=0,b=1):return max(a,min(b,float(v)))
class PerformanceLearningService:
 def __init__(self,s:Session):self.s=s;self.repo=PerformanceLearningRepository(s)
 @staticmethod
 def metrics(returns:list[float])->PerformanceMetrics:
  if not returns:return PerformanceMetrics(0,0,0,0,0,0,0,0,0,0)
  wins=[r for r in returns if r>0];losses=[r for r in returns if r<0];flats=len(returns)-len(wins)-len(losses);gross_win=sum(wins);gross_loss=abs(sum(losses));pf=round(gross_win/gross_loss,4) if gross_loss else (999.0 if gross_win else 0.0)
  equity=1.0;peak=1.0;dd=0.0
  for r in returns:equity*=1+r/100;peak=max(peak,equity);dd=min(dd,(equity/peak-1)*100)
  return PerformanceMetrics(len(returns),len(wins),len(losses),flats,round(len(wins)/len(returns)*100,2),round(mean(returns),4),round(median(returns),4),pf,round(mean(returns),4),round(abs(dd),4))
 @staticmethod
 def calibration(rows:list[dict])->tuple[CalibrationBucket,...]:
  out=[]
  for lo in (0,.2,.4,.6,.8):
   hi=lo+.2;bucket=[x for x in rows if lo<=x['predicted_probability']<(hi if hi<1 else 1.00001)]
   if bucket:
    pred=mean(x['predicted_probability'] for x in bucket);obs=mean(1 if x['realized_return_pct']>0 else 0 for x in bucket);out.append(CalibrationBucket(lo,hi,len(bucket),round(pred,4),round(obs,4),round(abs(pred-obs),4)))
  return tuple(out)
 @staticmethod
 def decision_quality(rows:list[dict])->DecisionQuality:
  if not rows:return DecisionQuality(0,0,0,0,0)
  aligned=[x for x in rows if x.get('decision_followed',True)];overrides=[x for x in rows if not x.get('decision_followed',True)];prof=[x for x in aligned if x['realized_return_pct']>0];avoidable=[x for x in rows if x['realized_return_pct']<0 and x.get('recommended_action')=='CLOSE' and x.get('decision_followed') is False]
  n=len(rows);return DecisionQuality(round(len(aligned)/n*100,2),round(len(overrides)/n*100,2),round(len(prof)/max(len(aligned),1)*100,2),round(len(avoidable)/n*100,2),n)
 @staticmethod
 def recommendations(rows:list[dict],by_strategy:dict[str,PerformanceMetrics])->tuple[LearningRecommendation,...]:
  rec=[]
  for strategy,m in by_strategy.items():
   if m.sample_size>=10 and m.expectancy_pct<0:rec.append(LearningRecommendation('SCANNER_WEIGHT',strategy,1.0,.85,.80,m.sample_size,'Negative governed expectancy warrants a bounded ranking reduction',{'expectancy_pct':m.expectancy_pct,'win_rate':m.win_rate}))
   elif m.sample_size>=10 and m.expectancy_pct>2 and m.win_rate>=55:rec.append(LearningRecommendation('SCANNER_WEIGHT',strategy,1.0,1.10,.78,m.sample_size,'Positive expectancy and win rate support a bounded ranking increase',{'expectancy_pct':m.expectancy_pct,'win_rate':m.win_rate}))
  cal=PerformanceLearningService.calibration(rows)
  if cal and sum(b.calibration_error*b.count for b in cal)/sum(b.count for b in cal)>.12:rec.append(LearningRecommendation('PROBABILITY_CALIBRATION','global',1.0,1.0,.85,len(rows),'Observed probability calibration error exceeds governance threshold',{'buckets':[b.to_dict() for b in cal]}))
  return tuple(rec)
 @staticmethod
 def build_report(rows:list[dict],portfolio_id='PAPER-PRIMARY',report_id='preview')->LearningReport:
  returns=[float(x['realized_return_pct']) for x in rows];groups={};dirs={}
  for x in rows:groups.setdefault(x.get('strategy','UNKNOWN'),[]).append(float(x['realized_return_pct']));dirs.setdefault(x.get('direction','UNKNOWN'),[]).append(float(x['realized_return_pct']))
  bs={k:PerformanceLearningService.metrics(v) for k,v in groups.items()};bd={k:PerformanceLearningService.metrics(v) for k,v in dirs.items()};return LearningReport(report_id,portfolio_id,now(),None,None,PerformanceLearningService.metrics(returns),bs,bd,PerformanceLearningService.calibration(rows),PerformanceLearningService.decision_quality(rows),PerformanceLearningService.recommendations(rows,bs),{'automatic_activation':False,'minimum_sample_size':10,'maximum_weight_change_pct':15,'requires_human_approval':True,'analytics_version':ANALYTICS_VERSION})
 def capture_position(self,position_id,actor):
  p=self.s.get(ManagedPositionModel,position_id)
  if not p:raise KeyError('Position not found')
  old=self.repo.observation(position_id,p.version)
  if old:return self.dto_observation(old)
  attrs=list(self.s.query(PositionAttributionModel).filter(PositionAttributionModel.position_id==position_id).order_by(PositionAttributionModel.generated_at.desc()).limit(1));a=attrs[0].payload_json if attrs else {}
  ret=float(a.get('outcome_return_pct',p.realized_pnl/max(p.entry_value,1)*100 if p.state=='CLOSED' else p.mark_json.get('unrealized_return_pct',0)));prob=float(p.metadata_json.get('predicted_probability',p.health_json.get('confidence',.5)));decision_followed=p.metadata_json.get('decision_followed',True)
  payload={'recommended_action':p.decision_json.get('action'),'decision_followed':decision_followed,'health_score':p.health_json.get('score'),'attribution':a,'paper_only':True}
  m=PerformanceObservationModel(observation_id=f'OBS-{uuid4().hex.upper()}',position_id=p.position_id,position_version=p.version,portfolio_id=p.portfolio_id,opportunity_id=p.opportunity_id,strategy=p.strategy,direction=p.direction,opened_at=p.opened_at,closed_at=p.closed_at,predicted_probability=clamp(prob),realized_return_pct=ret,outcome='WIN' if ret>0 else 'LOSS' if ret<0 else 'FLAT',payload_json=payload,observed_at=now());self.repo.add(m);self._event(m.observation_id,'OBSERVATION_CAPTURED',actor,'Captured immutable performance observation',payload);self.s.commit();return self.dto_observation(m)
 def generate_report(self,portfolio_id,actor):
  rows=[self.dto_observation(x) for x in self.repo.observations(portfolio_id)];report=self.build_report(rows,portfolio_id,f'PLR-{uuid4().hex.upper()}');d=report.to_dict();m=PerformanceLearningReportModel(report_id=report.report_id,portfolio_id=portfolio_id,window_start=report.window_start,window_end=report.window_end,generated_at=report.generated_at,analytics_version=ANALYTICS_VERSION,payload_json=d,generated_by=actor);self.repo.add(m);self._event(m.report_id,'REPORT_GENERATED',actor,'Generated governed performance-learning report',{'sample_size':report.overall.sample_size});self.s.commit();return d
 def propose_policy(self,name,parameters,evidence,actor,reason):
  prior=self.repo.policies(name);version=(prior[0].version+1) if prior else 1
  for k,v in parameters.items():
   if 'weight' in k.lower() and not .85<=float(v)<=1.15:raise ValueError('Learning weight changes are bounded to +/-15%')
  m=LearningPolicyModel(policy_id=f'LP-{uuid4().hex.upper()}',policy_name=name,version=version,state='DRAFT',expected_previous_version=prior[0].version if prior else None,parameters_json=parameters,evidence_json=evidence,reason=reason,created_by=actor,approved_by=None,created_at=now(),updated_at=now(),activated_at=None);self.repo.add(m);self._event(m.policy_id,'POLICY_PROPOSED',actor,reason,{'version':version,'parameters':parameters});self.s.commit();return self.dto_policy(m)
 def transition_policy(self,id,target,actor,reason):
  m=self.repo.policy(id)
  if not m:raise KeyError('Policy not found')
  allowed={'DRAFT':{'REVIEW','RETIRED'},'REVIEW':{'APPROVED','DRAFT','RETIRED'},'APPROVED':{'ACTIVE','RETIRED'},'ACTIVE':{'RETIRED'},'RETIRED':set()}
  if target not in allowed[m.state]:raise ValueError(f'Invalid policy transition {m.state} -> {target}')
  if target=='ACTIVE':
   for x in self.repo.policies(m.policy_name):
    if x.state=='ACTIVE':x.state='RETIRED';x.updated_at=now()
   m.activated_at=now()
  m.state=target;m.updated_at=now();m.approved_by=actor if target in ('APPROVED','ACTIVE') else m.approved_by;self._event(m.policy_id,'POLICY_STATE_CHANGED',actor,reason,{'state':target,'version':m.version});self.s.commit();return self.dto_policy(m)
 def _event(self,entity,event,actor,reason,payload):self.repo.add(LearningAuditEventModel(event_id=f'PLE-{uuid4().hex.upper()}',entity_id=entity,event_type=event,actor=actor,reason=reason,event_timestamp=now(),payload_json=payload))
 @staticmethod
 def dto_observation(m):return {'observation_id':m.observation_id,'position_id':m.position_id,'position_version':m.position_version,'portfolio_id':m.portfolio_id,'opportunity_id':m.opportunity_id,'strategy':m.strategy,'direction':m.direction,'opened_at':m.opened_at,'closed_at':m.closed_at,'predicted_probability':m.predicted_probability,'realized_return_pct':m.realized_return_pct,'outcome':m.outcome,'observed_at':m.observed_at,**m.payload_json}
 @staticmethod
 def dto_policy(m):return {'policy_id':m.policy_id,'policy_name':m.policy_name,'version':m.version,'state':m.state,'expected_previous_version':m.expected_previous_version,'parameters':m.parameters_json,'evidence':m.evidence_json,'reason':m.reason,'created_by':m.created_by,'approved_by':m.approved_by,'created_at':m.created_at,'updated_at':m.updated_at,'activated_at':m.activated_at}
