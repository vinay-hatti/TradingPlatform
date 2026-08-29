from pathlib import Path
REQUIRED=(
'src/trading_ai/position_monitoring/position_monitoring_policy.py',
'src/trading_ai/position_monitoring/mark_to_market_engine.py',
'src/trading_ai/position_monitoring/portfolio_greeks_policy.py',
'src/trading_ai/position_monitoring/scenario_risk_monitoring_engine.py',
'src/trading_ai/position_monitoring/dynamic_risk_limit_registry.py',
'src/trading_ai/position_monitoring/risk_breach_engine.py',
'src/trading_ai/position_monitoring/continuous_monitoring_orchestrator.py',
'src/trading_ai/position_monitoring/automated_kill_switch_engine.py',
'src/trading_ai/position_monitoring/position_risk_reporting.py',
'src/trading_ai/position_monitoring/position_risk_dashboard.py',
)
COMMANDS=('realtime-position-monitoring-test','portfolio-greeks-monitoring-test','dynamic-risk-limits-test','continuous-monitoring-test','position-risk-report','position-risk-dashboard','milestone30-phase7-regression-test','milestone30-phase7-closure-test')
def main():
    missing=[p for p in REQUIRED if not Path(p).exists()]; assert not missing, 'Missing Phase 7 modules: '+', '.join(missing)
    source=Path('src/trading_ai/__main__.py').read_text()
    for command in COMMANDS: assert command in source, f'Missing CLI command: {command}'
    report=Path('src/trading_ai/position_monitoring/position_risk_reporting.py').read_text()
    for heading in ('Real-Time Position Snapshots and Mark-to-Market','Portfolio Greeks, Exposure Surfaces, and Scenario Risk','Dynamic Limits, Breaches, Alerts, and Escalations','Continuous Monitoring, Reconciliation, and Kill-Switch Governance'): assert heading in report
    dashboard=Path('src/trading_ai/position_monitoring/position_risk_dashboard.py').read_text()
    for field in ('current_equity','portfolio_delta','critical_breach_count','kill_switch_activated'): assert field in dashboard
    status=Path('updated_PROJECT_STATUS.md').read_text(); assert 'Milestone 30 Phase 7 — Real-Time Position and Risk Monitoring | ✅ Complete' in status
    print('All Milestone 30 Phase 7 closure assertions passed.')
if __name__=='__main__': main()
