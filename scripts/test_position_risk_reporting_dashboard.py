from __future__ import annotations
import tempfile, json
from pathlib import Path
from trading_ai.position_monitoring.position_risk_reporting import PositionRiskOperationalReport
from trading_ai.position_monitoring.position_risk_dashboard import PositionRiskDashboardBuilder

def main():
    position={'snapshot_id':'snap-1','account_id':'PAPER-001','current_equity':100500.0,'total_pnl':500.0,'gross_exposure':12000.0,'net_exposure':2000.0,'intraday_drawdown':500.0,'open_position_count':3,'stale_position_count':0}
    greeks={'snapshot_id':'greeks-1','account_id':'PAPER-001','delta':100.0,'gamma':5.0,'vega':50.0,'theta':-10.0,'rho':4.0,'worst_scenario_loss':2500.0,'worst_scenario_id':'AAPL|U-0.1'}
    breach={'breach_id':'b-1','account_id':'PAPER-001','metric':'DELTA','scope_type':'ACCOUNT','scope_value':'PAPER-001','observed_value':100.0,'limit_value':80.0,'severity':'CRITICAL','status':'OPEN','occurrence_count':2}
    alert={'alert_id':'a-1','breach_id':'b-1','severity':'CRITICAL','channel':'PAGER','destination':'on-call-risk','status':'SENT'}
    cycle={'cycle_id':'c-1','account_id':'PAPER-001','sequence_number':1,'state':'COMPLETED','completed_stages':('POSITION_SNAPSHOT','GREEKS_MONITORING'),'failed_stage':None,'breach_count':1,'reconciliation_allowed':True,'kill_switch_activated':True}
    with tempfile.TemporaryDirectory() as temp:
        report=PositionRiskOperationalReport().generate(position_snapshots=(position,),greeks_states=(greeks,),breaches=(breach,),alerts=(alert,),cycles=(cycle,),path=Path(temp)/'report.html')
        html=report.read_text();
        for heading in ('Real-Time Position Snapshots and Mark-to-Market','Portfolio Greeks, Exposure Surfaces, and Scenario Risk','Dynamic Limits, Breaches, Alerts, and Escalations','Continuous Monitoring, Reconciliation, and Kill-Switch Governance'): assert heading in html
        builder=PositionRiskDashboardBuilder(); payload=builder.build_payload(position_state=position,greeks_state=greeks,breaches=(breach,),alerts=(alert,),cycle_state=cycle)
        assert payload['summary']['critical_breach_count']==1
        assert payload['summary']['kill_switch_activated'] is True
        path=builder.write(payload,Path(temp)/'dashboard.json'); saved=json.loads(path.read_text()); assert saved['schema_version']=='1.0'; assert saved['summary']['account_id']=='PAPER-001'
    print('All position/risk reporting and dashboard integration assertions passed.')
if __name__=='__main__': main()
