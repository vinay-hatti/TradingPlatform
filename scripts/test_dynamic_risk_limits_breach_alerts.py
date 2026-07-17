from __future__ import annotations
from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path
from trading_ai.position_monitoring.dynamic_risk_limit_policy import DynamicRiskLimitPolicy
from trading_ai.position_monitoring.dynamic_risk_limit_profile import DynamicRiskLimitProfile
from trading_ai.position_monitoring.dynamic_risk_limit_registry import DynamicRiskLimitRegistry
from trading_ai.position_monitoring.dynamic_risk_monitoring_service import DynamicRiskMonitoringService
from trading_ai.position_monitoring.risk_breach_repository import JsonRiskBreachRepository
from trading_ai.position_monitoring.risk_alert_repository import JsonRiskAlertRepository
from trading_ai.position_monitoring.dynamic_risk_limit_serialization import dumps

class Obj:
    def __init__(self,**kwargs): self.__dict__.update(kwargs)

def main():
    now=datetime.now(timezone.utc)
    effective=(now-timedelta(minutes=1)).isoformat()
    profiles=(
        DynamicRiskLimitProfile(effective_from=effective,profile_id='gross-account',scope_type='ACCOUNT',scope_value='PAPER-001',metric='GROSS_EXPOSURE',warning_limit=5000,severe_limit=6000,critical_limit=7000,precedence=100),
        DynamicRiskLimitProfile(effective_from=effective,profile_id='delta-account',scope_type='ACCOUNT',scope_value='PAPER-001',metric='DELTA',warning_limit=30,severe_limit=40,critical_limit=50,precedence=100),
        DynamicRiskLimitProfile(effective_from=effective,profile_id='aapl-delta',scope_type='UNDERLYING',scope_value='AAPL',metric='UNDERLYING_DELTA',warning_limit=20,severe_limit=30,critical_limit=40,precedence=300),
        DynamicRiskLimitProfile(effective_from=effective,profile_id='scenario-account',scope_type='ACCOUNT',scope_value='PAPER-001',metric='WORST_SCENARIO_LOSS',warning_limit=500,severe_limit=750,critical_limit=1000,precedence=100),
    )
    registry=DynamicRiskLimitRegistry(profiles)
    resolved=registry.resolve(metric='UNDERLYING_DELTA',scopes=(('ACCOUNT','PAPER-001'),('UNDERLYING','AAPL')),as_of=now)
    assert resolved is not None and resolved.profile_id=='aapl-delta'

    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        service=DynamicRiskMonitoringService(registry=registry,policy=DynamicRiskLimitPolicy(critical_escalation_after_seconds=1,severe_escalation_after_seconds=1),breach_repository=JsonRiskBreachRepository(root/'breaches.json'),alert_repository=JsonRiskAlertRepository(root/'alerts.json'))
        position=Obj(account_id='PAPER-001',snapshot_id='snapshot-1',gross_exposure=6500,net_exposure=0,intraday_drawdown=0,drawdown_pct=0,total_pnl=100)
        underlying=Obj(underlying_symbol='AAPL',delta=45,gamma=1,vega=2,scenario_loss=100)
        greeks=Obj(account_id='PAPER-001',snapshot_id='greeks-1',delta=55,gamma=2,vega=3,theta=-1,rho=1,worst_scenario_loss=1200,worst_scenario_loss_pct_of_equity=0.012,by_underlying=(underlying,))
        decision=service.evaluate_monitoring_states(position_state=position,greeks_state=greeks)
        assert not decision.allowed
        assert decision.recommendation=='KILL_SWITCH_REVIEW'
        assert any(b.metric=='GROSS_EXPOSURE' and b.severity=='SEVERE' for b in decision.breaches)
        assert any(b.metric=='DELTA' and b.severity=='CRITICAL' for b in decision.breaches)
        assert any(b.metric=='UNDERLYING_DELTA' and b.severity=='CRITICAL' for b in decision.breaches)
        assert any(b.metric=='WORST_SCENARIO_LOSS' and b.severity=='CRITICAL' for b in decision.breaches)
        assert any(a.channel=='PAGER' for a in decision.alerts)

        second=service.evaluate_monitoring_states(position_state=position,greeks_state=greeks)
        delta_breach=next(b for b in second.breaches if b.metric=='DELTA')
        assert delta_breach.occurrence_count==2
        acknowledged=service.breach_repository.acknowledge(delta_breach.breach_id,'risk-operator')
        assert acknowledged.status=='ACKNOWLEDGED'
        resolved_breach=service.breach_repository.resolve(delta_breach.breach_id,'Exposure reduced')
        assert resolved_breach.status=='RESOLVED'

        old=now-timedelta(seconds=10)
        direct=service.evaluate(account_id='PAPER-001',snapshot_id='snapshot-old',metrics=({'metric':'DELTA','value':55,'scope_type':'ACCOUNT','scope_value':'PAPER-001','scopes':(('ACCOUNT','PAPER-001'),)},),as_of=old)
        later=service.evaluate(account_id='PAPER-001',snapshot_id='snapshot-later',metrics=({'metric':'DELTA','value':55,'scope_type':'ACCOUNT','scope_value':'PAPER-001','scopes':(('ACCOUNT','PAPER-001'),)},),as_of=now)
        assert later.escalations
        assert later.escalations[0].target_role=='RISK_MANAGER'

        payload=dumps(decision)
        assert '"recommendation": "KILL_SWITCH_REVIEW"' in payload
        assert '"alert_count"' in payload
    print('All dynamic risk-limit, breach-detection, alert-routing, and escalation assertions passed.')

if __name__=='__main__': main()
