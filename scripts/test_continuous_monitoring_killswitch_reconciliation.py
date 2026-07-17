from __future__ import annotations
from datetime import datetime, timezone, timedelta
import tempfile
from pathlib import Path
from trading_ai.broker.broker_status_profile import BrokerPositionProfile
from trading_ai.risk_gateway.trading_control_repository import JsonTradingControlRepository
from trading_ai.risk_gateway.trading_control_service import TradingControlService
from trading_ai.position_monitoring.automated_kill_switch_engine import AutomatedKillSwitchEngine
from trading_ai.position_monitoring.broker_position_reconciliation_engine import BrokerPositionReconciliationEngine
from trading_ai.position_monitoring.continuous_monitoring_orchestrator import ContinuousMonitoringOrchestrator
from trading_ai.position_monitoring.continuous_monitoring_repository import JsonContinuousMonitoringRepository
from trading_ai.position_monitoring.continuous_monitoring_serialization import dumps
from trading_ai.position_monitoring.dynamic_risk_limit_profile import DynamicRiskLimitProfile
from trading_ai.position_monitoring.dynamic_risk_limit_registry import DynamicRiskLimitRegistry
from trading_ai.position_monitoring.dynamic_risk_monitoring_service import DynamicRiskMonitoringService
from trading_ai.position_monitoring.position_monitoring_profile import RealTimePositionSnapshot, RealTimeQuoteSnapshot
from trading_ai.position_monitoring.position_monitoring_service import PositionMonitoringService
from trading_ai.position_monitoring.position_snapshot_repository import JsonPositionSnapshotRepository
from trading_ai.position_monitoring.portfolio_greeks_profile import RealTimePositionGreeks
from trading_ai.position_monitoring.portfolio_greeks_service import PortfolioGreeksMonitoringService
from trading_ai.position_monitoring.portfolio_greeks_repository import JsonPortfolioGreeksRepository
from trading_ai.position_monitoring.risk_breach_repository import JsonRiskBreachRepository
from trading_ai.position_monitoring.risk_alert_repository import JsonRiskAlertRepository

def main():
 now=datetime.now(timezone.utc); effective=(now-timedelta(minutes=1)).isoformat()
 with tempfile.TemporaryDirectory() as temp:
  root=Path(temp); account='PAPER-001'
  position_service=PositionMonitoringService(repository=JsonPositionSnapshotRepository(root/'snapshots.json'))
  greeks_service=PortfolioGreeksMonitoringService(repository=JsonPortfolioGreeksRepository(root/'greeks.json'))
  registry=DynamicRiskLimitRegistry((
   DynamicRiskLimitProfile('delta-account','ACCOUNT',account,'DELTA',100,150,200,effective_from=effective),
   DynamicRiskLimitProfile('gross-account','ACCOUNT',account,'GROSS_EXPOSURE',100000,150000,200000,direction='MAX',effective_from=effective),
  ))
  dynamic=DynamicRiskMonitoringService(registry=registry,breach_repository=JsonRiskBreachRepository(root/'breaches.json'),alert_repository=JsonRiskAlertRepository(root/'alerts.json'))
  controls=TradingControlService(JsonTradingControlRepository(root/'controls.json'))
  reconcile=BrokerPositionReconciliationEngine(); kill=AutomatedKillSwitchEngine(trading_control_service=controls)
  repo=JsonContinuousMonitoringRepository(root/'cycles.json')
  orchestrator=ContinuousMonitoringOrchestrator(position_service=position_service,greeks_service=greeks_service,dynamic_limit_service=dynamic,reconciliation_engine=reconcile,kill_switch_engine=kill,repository=repo)
  positions=(RealTimePositionSnapshot('pos-1',account,'AAPL_200C','AAPL','OPTION','LONG',2,5,100,sector='TECHNOLOGY',strategy_name='LONG_CALL'),)
  quotes={'AAPL_200C':RealTimeQuoteSnapshot('AAPL_200C',6.4,6.6,6.5,now.isoformat(),'test')}
  greek=(RealTimePositionGreeks('pos-1','AAPL_200C','AAPL',2,100,'LONG',0.5,0.02,0.2,-0.05,0.1,205,timestamp=now.isoformat()),)
  broker=(BrokerPositionProfile('fake',account,'AAPL_200C','OPTION',2,5,multiplier=100),)
  platform=(BrokerPositionProfile('platform',account,'AAPL_200C','OPTION',2,5,multiplier=100),)
  result=orchestrator.run_cycle(account_id=account,position_kwargs={'account_id':account,'starting_equity':100000,'peak_equity':101000,'cash_balance':99000,'positions':positions,'quotes':quotes,'as_of':now,'snapshot_id':'pos-snap-1'},greeks_kwargs={'account_id':account,'snapshot_id':'greeks-snap-1','current_equity':100300,'option_position_ids':('pos-1',),'greeks':greek,'as_of':now},broker_positions=broker,platform_positions=platform)
  assert result.allowed and result.recommendation=='MONITOR';assert result.reconciliation_decision.allowed;assert not result.kill_switch_decision.activated;assert repo.get(result.cycle_id).state=='COMPLETED'
  mismatch=(BrokerPositionProfile('fake',account,'AAPL_200C','OPTION',3,5,multiplier=100),)
  halted=orchestrator.run_cycle(account_id=account,position_kwargs={'account_id':account,'starting_equity':100000,'peak_equity':101000,'cash_balance':99000,'positions':positions,'quotes':quotes,'as_of':now,'snapshot_id':'pos-snap-2'},greeks_kwargs={'account_id':account,'snapshot_id':'greeks-snap-2','current_equity':100300,'option_position_ids':('pos-1',),'greeks':greek,'as_of':now},broker_positions=mismatch,platform_positions=platform)
  assert not halted.allowed;assert halted.kill_switch_decision.activated;assert not halted.reconciliation_decision.allowed
  state=controls.state(account);assert state.kill_switch.automatic_active;assert any(h.active and h.scope_type=='ACCOUNT' for h in state.halts)
  critical_greek=(RealTimePositionGreeks(**{**greek[0].__dict__,'delta':2.0}),)
  critical=orchestrator.run_cycle(account_id=account,position_kwargs={'account_id':account,'starting_equity':100000,'peak_equity':101000,'cash_balance':99000,'positions':positions,'quotes':quotes,'as_of':now,'snapshot_id':'pos-snap-3'},greeks_kwargs={'account_id':account,'snapshot_id':'greeks-snap-3','current_equity':100300,'option_position_ids':('pos-1',),'greeks':critical_greek,'as_of':now},broker_positions=broker,platform_positions=platform)
  assert not critical.allowed;assert critical.breach_decision.recommendation=='KILL_SWITCH_REVIEW';assert critical.kill_switch_decision.activated
  failed=orchestrator.run_cycle(account_id=account,position_kwargs={'account_id':account,'starting_equity':100000,'peak_equity':101000,'cash_balance':99000,'positions':positions,'quotes':{},'as_of':now,'snapshot_id':'pos-fail'},greeks_kwargs={'account_id':account,'snapshot_id':'greeks-fail','current_equity':100000,'option_position_ids':('pos-1',),'greeks':greek,'as_of':now},broker_positions=broker,platform_positions=platform)
  assert not failed.allowed;assert failed.cycle_state.state=='FAILED';assert failed.kill_switch_decision.activated
  payload=dumps(critical);assert 'KILL_SWITCH_REVIEW' in payload and 'kill_switch_activated' in payload
 print('All automated kill-switch, broker reconciliation, and continuous-monitoring assertions passed.')
if __name__=='__main__':main()
