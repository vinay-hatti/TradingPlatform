import json,tempfile
from pathlib import Path
from trading_ai.portfolio_management.phase2_workflow_service import Milestone36Phase2WorkflowService

def main():
  with tempfile.TemporaryDirectory() as t:
    r=Path(t); reg=r/'registry.json'; cand=r/'reports/m35/phase5/dashboard/opportunity_rankings/opportunity_rankings.json'; out=r/'reports/m36/phase2'; cand.parent.mkdir(parents=True)
    reg.write_text(json.dumps({'account':{'portfolio_id':'PRIMARY','initial_capital':100000},'cash_balance':100000,'net_liquidation_value':100000,'positions':[]}))
    cand.write_text(json.dumps({'ranked_opportunities':[{'ranking_score':92,'raw_ranking_score':94,'allowed':True,'selected':True,'action':'TRADE','opportunity':{'symbol':'AAPL','strategy':'BULL_CALL_SPREAD','direction':'CALL','strategy_score':90,'portfolio_fit_score':85,'capital_required':250,'maximum_loss':250,'expected_profit':200,'expected_return_pct':80,'readiness':'READY','recommendation':'TRADE','sector':'TECHNOLOGY','correlation_group':'MEGA_CAP','risk_profile':'DEFINED_RISK','greeks':{'delta':20,'gamma':1,'theta':-4,'vega':12,'rho':2}}}]}))
    s=Milestone36Phase2WorkflowService(); assert s.discover_candidate_file(r/'reports/m35')==cand
    result=s.run(cand,reg,out)
    assert result.status=='COMPLETE' and result.order_count==1
    for f in ('portfolio_construction.json','capital_allocation.json','constraint_validation.json','scenario_comparison.json','execution_handoff.json','phase2_closure.json','phase2_closure.html'): assert (out/f).exists()
  print('Milestone 36 Phase 2 Step 6 workflow assertions passed.')
if __name__=='__main__': main()
