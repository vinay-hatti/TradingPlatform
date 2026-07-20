from types import SimpleNamespace as N
from trading_ai.research_workstation.dashboard import ResearchDashboardEngine,research_dashboard_payload

def main():
    case=N(case_id='CASE-1',symbol='AAPL',strategy_name='BULL_PUT_SPREAD',primary_thesis='Bullish thesis',evidence=(N(reliability_score=.9),))
    comp=N(best_scenario_id='BULL',recommendation=N(action='BUY',confidence=.8))
    journal=N(journal_id='J-1',case_id='CASE-1',decision_confidence=.8,decision_status='APPROVED_FOR_EXECUTION',approval_status='APPROVED',decision_rationale='Approved',primary_risks=('Gap risk',),monitoring_plan=('Monitor',))
    thesis=N(validation_status='CONFIRMED',confirmation_score=.85,thesis_summary='Confirmed')
    attr=N(case_id='CASE-1',journal_id='J-1',forecast_accuracy=N(overall_forecast_accuracy=.82),scenario_calibration=N(calibration_score=.8),thesis_validation=thesis,decision_quality_score=.84,decision_quality_grade='B',outcome_status='PROFITABLE',positive_factors=('Strong evidence',),warnings=(),remediation_actions=())
    result=ResearchDashboardEngine().build(dashboard_id='D-1',research_case=case,scenario_comparison=comp,decision_journal=journal,outcome_attribution=attr,thesis_validation=N(case_id='CASE-1',thesis_validation=thesis))
    assert result.phase_completion.phase_status=='COMPLETE'; assert result.scorecard.institutional_ready; assert len(result.scorecard.kpis)==9
    assert research_dashboard_payload(result)['dashboard_id']=='D-1'
    print('All Milestone 34 Phase 4 Step 5 dashboard assertions passed.')
if __name__=='__main__': main()
