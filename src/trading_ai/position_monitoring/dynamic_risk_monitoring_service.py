from __future__ import annotations
from dataclasses import replace
from datetime import datetime
from typing import Any
from .dynamic_risk_limit_policy import DynamicRiskLimitPolicy
from .dynamic_risk_limit_profile import RiskBreachMonitoringDecision
from .dynamic_risk_limit_registry import DynamicRiskLimitRegistry
from .risk_breach_engine import RiskBreachEngine
from .risk_breach_repository import JsonRiskBreachRepository
from .risk_alert_router import RiskAlertRouter
from .risk_alert_repository import JsonRiskAlertRepository
from .risk_escalation_engine import RiskEscalationEngine

class DynamicRiskMonitoringService:
    def __init__(self, *, registry: DynamicRiskLimitRegistry, policy: DynamicRiskLimitPolicy|None=None, breach_repository: JsonRiskBreachRepository|None=None, alert_repository: JsonRiskAlertRepository|None=None) -> None:
        self.policy=policy or DynamicRiskLimitPolicy(); self.registry=registry; self.breach_engine=RiskBreachEngine(); self.breach_repository=breach_repository or JsonRiskBreachRepository(); self.alert_repository=alert_repository or JsonRiskAlertRepository(); self.router=RiskAlertRouter(); self.escalation=RiskEscalationEngine(self.policy)

    @staticmethod
    def _value(obj: Any,name: str,default=None):
        if obj is None:return default
        if isinstance(obj,dict):return obj.get(name,default)
        return getattr(obj,name,default)

    def evaluate(self, *, account_id: str, snapshot_id: str, metrics: tuple[dict[str,Any],...], as_of: datetime|None=None) -> RiskBreachMonitoringDecision:
        breaches=[]; alerts=[]; escalations=[]; warnings=[]
        for item in metrics:
            scopes=tuple(item.get('scopes',(('ACCOUNT',account_id),)))
            limit=self.registry.resolve(metric=item['metric'],scopes=scopes,as_of=as_of)
            if limit is None:
                warnings.append(f"NO_ACTIVE_LIMIT:{item['metric']}:{item.get('scope_value',account_id)}")
                if self.policy.require_active_profile and self.policy.fail_closed: continue
                continue
            breach=self.breach_engine.detect(account_id=account_id,snapshot_id=snapshot_id,metric=item['metric'],scope_type=item.get('scope_type',limit.scope_type),scope_value=item.get('scope_value',limit.scope_value),observed_value=float(item['value']),limit=limit,detected_at=as_of)
            if breach is None: continue
            breach=self.breach_repository.save_or_increment(breach); breaches.append(breach)
            routed=self.router.route(breach); self.alert_repository.save_all(routed); alerts.extend(routed)
            generated=self.escalation.evaluate(breach,as_of=as_of); escalations.extend(generated)
            if generated:
                self.breach_repository.save_or_increment(replace(breach,escalation_level=generated[-1].level,occurrence_count=max(0,breach.occurrence_count-1)))
        critical=any(b.severity=='CRITICAL' for b in breaches)
        severe=any(b.severity=='SEVERE' for b in breaches)
        return RiskBreachMonitoringDecision(valid=True,allowed=not critical,account_id=account_id,snapshot_id=snapshot_id,recommendation='KILL_SWITCH_REVIEW' if critical else 'ESCALATE' if severe else 'MONITOR',breaches=tuple(breaches),alerts=tuple(alerts),escalations=tuple(escalations),warnings=tuple(warnings),rejection_reasons=tuple(f'{b.severity}:{b.metric}:{b.scope_value}' for b in breaches if b.severity=='CRITICAL'),metadata={'breach_count':len(breaches),'alert_count':len(alerts),'escalation_count':len(escalations)})

    def evaluate_monitoring_states(self, *, position_state: Any, greeks_state: Any) -> RiskBreachMonitoringDecision:
        account_id=self._value(position_state,'account_id') or self._value(greeks_state,'account_id')
        snapshot_id=self._value(greeks_state,'snapshot_id') or self._value(position_state,'snapshot_id')
        metrics=[]
        for metric in ('gross_exposure','net_exposure','intraday_drawdown','drawdown_pct','total_pnl'):
            value=self._value(position_state,metric)
            if value is not None: metrics.append({'metric':metric.upper(),'value':value,'scope_type':'ACCOUNT','scope_value':account_id,'scopes':(('ACCOUNT',account_id),)})
        for metric in ('delta','gamma','vega','theta','rho','worst_scenario_loss','worst_scenario_loss_pct_of_equity'):
            value=self._value(greeks_state,metric)
            if value is not None: metrics.append({'metric':metric.upper(),'value':value,'scope_type':'ACCOUNT','scope_value':account_id,'scopes':(('ACCOUNT',account_id),)})
        for exposure in self._value(greeks_state,'by_underlying',()) or ():
            symbol=self._value(exposure,'underlying_symbol')
            for metric in ('delta','gamma','vega','scenario_loss'):
                value=self._value(exposure,metric)
                if value is not None: metrics.append({'metric':f'UNDERLYING_{metric.upper()}','value':value,'scope_type':'UNDERLYING','scope_value':symbol,'scopes':(('UNDERLYING',symbol),('ACCOUNT',account_id))})
        return self.evaluate(account_id=account_id,snapshot_id=snapshot_id,metrics=tuple(metrics))
