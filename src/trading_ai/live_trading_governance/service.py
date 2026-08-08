from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from .models import *

def now(): return datetime.now(timezone.utc)
class LiveTradingGovernanceService:
    CONFIRM='ENABLE LIVE ROUTING FOR {portfolio_id}'
    def __init__(self, session): self.s=session
    def _audit(self,p,e,a,r='',payload=None): self.s.add(LiveTradingAuditEventModel(portfolio_id=p,event_type=e,actor=a,reason=r,payload_json=payload or {}))
    def latest_policy(self,p): return self.s.scalar(select(LiveTradingPolicyModel).where(LiveTradingPolicyModel.portfolio_id==p).order_by(LiveTradingPolicyModel.version.desc()))
    def create_policy(self,p,actor,payload):
        prior=self.latest_policy(p); v=(prior.version+1 if prior else 1)
        row=LiveTradingPolicyModel(portfolio_id=p,version=v,status='DRAFT',environment='LIVE',live_routing_enabled=False,max_trade_loss_pct=float(payload.get('max_trade_loss_pct',.5)),max_daily_loss_pct=float(payload.get('max_daily_loss_pct',1)),max_portfolio_heat_pct=float(payload.get('max_portfolio_heat_pct',10)),max_contracts=int(payload.get('max_contracts',1)),max_open_orders=int(payload.get('max_open_orders',5)),allowed_symbols_json=sorted(set(payload.get('allowed_symbols',[]))),allowed_strategies_json=sorted(set(payload.get('allowed_strategies',[]))),allowed_order_types_json=sorted(set(payload.get('allowed_order_types',['LMT']))),metadata_json={'created_by':actor,**payload.get('metadata',{})},updated_at=now())
        self.s.add(row);self._audit(p,'POLICY_CREATED',actor,payload={'policy_id':row.policy_id,'version':v});self.s.commit();return self.policy_dict(row)
    def request_approval(self,p,actor,reason=''):
        pol=self.latest_policy(p)
        if not pol: raise ValueError('live trading policy not found')
        pol.status='PENDING_APPROVAL';pol.updated_at=now();r=LiveTradingApprovalModel(portfolio_id=p,policy_id=pol.policy_id,requested_by=actor,reason=reason,expires_at=now()+timedelta(hours=24));self.s.add(r);self._audit(p,'APPROVAL_REQUESTED',actor,reason,{'approval_id':r.approval_id});self.s.commit();return {'approval_id':r.approval_id,'status':r.status}
    def approve(self,approval_id,actor,reason=''):
        r=self.s.get(LiveTradingApprovalModel,approval_id)
        if not r: raise KeyError(approval_id)
        if r.requested_by==actor: raise PermissionError('maker-checker requires a different approver')
        if r.expires_at:
            expiry=r.expires_at if r.expires_at.tzinfo else r.expires_at.replace(tzinfo=timezone.utc)
            if expiry<now(): raise ValueError('approval expired')
        r.status='APPROVED';r.approved_by=actor;r.reason=reason or r.reason;r.updated_at=now();pol=self.s.get(LiveTradingPolicyModel,r.policy_id);pol.status='APPROVED';pol.updated_at=now();self._audit(r.portfolio_id,'POLICY_APPROVED',actor,r.reason,{'approval_id':approval_id});self.s.commit();return {'approval_id':approval_id,'status':'APPROVED'}
    def certify(self,p,actor,evidence=None):
        pol=self.latest_policy(p)
        if not pol or pol.status not in {'APPROVED','CERTIFIED','ACTIVE'}: raise ValueError('approved policy required')
        ev=evidence or {}; checks=[
          ('policy_approved',pol.status in {'APPROVED','CERTIFIED','ACTIVE'}),('live_disabled_during_certification',not pol.live_routing_enabled),('symbol_allowlist',bool(pol.allowed_symbols_json)),('strategy_allowlist',bool(pol.allowed_strategies_json)),('limit_order_only','LMT' in pol.allowed_order_types_json),('max_contracts_bounded',0<pol.max_contracts<=10),('portfolio_heat_bounded',0<pol.max_portfolio_heat_pct<=20),('production_readiness',bool(ev.get('platform_ready',False))),('broker_account_verified',bool(ev.get('broker_account_verified',False))),('dynamic_management_ready',bool(ev.get('management_ready',False))),('kill_switch_tested',bool(ev.get('kill_switch_tested',False)))]
        details=[{'check':n,'passed':bool(v)} for n,v in checks]; passed=sum(x['passed'] for x in details);failed=len(details)-passed
        run=LiveTradingCertificationRunModel(portfolio_id=p,policy_id=pol.policy_id,status='PASSED' if failed==0 else 'FAILED',passed_checks=passed,failed_checks=failed,checks_json=details,evidence_json=ev,completed_at=now());self.s.add(run)
        if failed==0: pol.status='CERTIFIED';pol.updated_at=now()
        self._audit(p,'CERTIFICATION_COMPLETED',actor,payload={'run_id':run.run_id,'status':run.status,'failed':failed});self.s.commit();return {'run_id':run.run_id,'status':run.status,'passed_checks':passed,'failed_checks':failed,'checks':details}
    def activate(self,p,actor,confirmation):
        pol=self.latest_policy(p); expected=self.CONFIRM.format(portfolio_id=p)
        if confirmation!=expected: raise ValueError(f'confirmation must exactly equal: {expected}')
        if not pol or pol.status!='CERTIFIED': raise ValueError('certified policy required')
        active=self.s.scalars(select(LiveTradingKillSwitchModel).where(LiveTradingKillSwitchModel.portfolio_id==p,LiveTradingKillSwitchModel.active==True)).all()
        if active: raise PermissionError('active kill switch blocks live activation')
        pol.status='ACTIVE';pol.live_routing_enabled=True;pol.updated_at=now();self._audit(p,'LIVE_ROUTING_ACTIVATED',actor,payload={'policy_id':pol.policy_id});self.s.commit();return self.status(p)
    def halt(self,p,actor,reason,scope='ACCOUNT',scope_value='*',action='BLOCK_NEW_ORDERS'):
        row=LiveTradingKillSwitchModel(portfolio_id=p,scope=scope,scope_value=scope_value,active=True,action=action,reason=reason,activated_by=actor);self.s.add(row);pol=self.latest_policy(p)
        if pol: pol.live_routing_enabled=False;pol.status='HALTED';pol.updated_at=now()
        self._audit(p,'KILL_SWITCH_ACTIVATED',actor,reason,{'switch_id':row.switch_id,'scope':scope,'action':action});self.s.commit();return {'switch_id':row.switch_id,'status':'ACTIVE'}
    def clear_halt(self,switch_id,actor,reason=''):
        row=self.s.get(LiveTradingKillSwitchModel,switch_id)
        if not row: raise KeyError(switch_id)
        row.active=False;row.cleared_by=actor;row.cleared_at=now();self._audit(row.portfolio_id,'KILL_SWITCH_CLEARED',actor,reason,{'switch_id':switch_id});self.s.commit();return {'switch_id':switch_id,'status':'CLEARED'}
    def evaluate_order(self,p,order,readiness=None):
        pol=self.latest_policy(p); blocks=[]; readiness=readiness or {}
        if not pol or pol.status!='ACTIVE' or not pol.live_routing_enabled: blocks.append('LIVE_ROUTING_DISABLED')
        if not readiness.get('platform_ready',False): blocks.append('PLATFORM_NOT_READY')
        if not readiness.get('execution_ready',False): blocks.append('EXECUTION_NOT_READY')
        if not readiness.get('portfolio_ready',False): blocks.append('PORTFOLIO_NOT_READY')
        if not readiness.get('management_ready',False): blocks.append('MANAGEMENT_NOT_READY')
        if pol:
            if order.get('symbol') not in pol.allowed_symbols_json: blocks.append('SYMBOL_NOT_ALLOWED')
            if order.get('strategy') not in pol.allowed_strategies_json: blocks.append('STRATEGY_NOT_ALLOWED')
            if order.get('order_type','').upper() not in pol.allowed_order_types_json: blocks.append('ORDER_TYPE_NOT_ALLOWED')
            if int(order.get('quantity',0))>pol.max_contracts: blocks.append('MAX_CONTRACTS_EXCEEDED')
            if float(order.get('maximum_loss_pct',999))>pol.max_trade_loss_pct: blocks.append('MAX_TRADE_LOSS_EXCEEDED')
        if self.s.scalar(select(LiveTradingKillSwitchModel).where(LiveTradingKillSwitchModel.portfolio_id==p,LiveTradingKillSwitchModel.active==True)): blocks.append('KILL_SWITCH_ACTIVE')
        decision='ALLOW' if not blocks else 'BLOCK';return {'decision':decision,'allowed':not blocks,'reasons':blocks,'policy_id':pol.policy_id if pol else None}
    def policy_dict(self,p): return {'policy_id':p.policy_id,'portfolio_id':p.portfolio_id,'version':p.version,'status':p.status,'environment':p.environment,'live_routing_enabled':p.live_routing_enabled,'limits':{'max_trade_loss_pct':p.max_trade_loss_pct,'max_daily_loss_pct':p.max_daily_loss_pct,'max_portfolio_heat_pct':p.max_portfolio_heat_pct,'max_contracts':p.max_contracts,'max_open_orders':p.max_open_orders},'allowed_symbols':p.allowed_symbols_json,'allowed_strategies':p.allowed_strategies_json,'allowed_order_types':p.allowed_order_types_json}
    def status(self,p):
        pol=self.latest_policy(p); approvals=self.s.scalars(select(LiveTradingApprovalModel).where(LiveTradingApprovalModel.portfolio_id==p).order_by(LiveTradingApprovalModel.created_at.desc())).all(); cert=self.s.scalar(select(LiveTradingCertificationRunModel).where(LiveTradingCertificationRunModel.portfolio_id==p).order_by(LiveTradingCertificationRunModel.started_at.desc())); switches=self.s.scalars(select(LiveTradingKillSwitchModel).where(LiveTradingKillSwitchModel.portfolio_id==p,LiveTradingKillSwitchModel.active==True)).all()
        return {'portfolio_id':p,'environment':'LIVE','live_routing_enabled':bool(pol and pol.live_routing_enabled),'policy':self.policy_dict(pol) if pol else None,'latest_certification':({'run_id':cert.run_id,'status':cert.status,'passed_checks':cert.passed_checks,'failed_checks':cert.failed_checks} if cert else None),'pending_approvals':sum(1 for x in approvals if x.status=='PENDING'),'active_kill_switches':[{'switch_id':x.switch_id,'scope':x.scope,'scope_value':x.scope_value,'action':x.action,'reason':x.reason} for x in switches],'status':'LIVE_READY' if pol and pol.status=='ACTIVE' and not switches else 'LIVE_DISABLED'}
