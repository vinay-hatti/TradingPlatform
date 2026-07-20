from types import SimpleNamespace as N
from trading_ai.research_workstation.dashboard import ResearchDashboardEngine

def main():
    case=N(case_id='C',symbol='X',strategy_name='S',primary_thesis='T',evidence=()); comp=N(best_scenario_id='B',recommendation=N(action='MONITOR',confidence=.5)); journal=N(journal_id='J',case_id='WRONG',decision_confidence=.5,decision_status='REVIEW_REQUIRED',approval_status='NOT_REVIEWED',decision_rationale='',primary_risks=(),monitoring_plan=()); thesis=N(validation_status='INCONCLUSIVE',confirmation_score=.2,thesis_summary='T'); attr=N(case_id='C',journal_id='WRONG',forecast_accuracy=N(overall_forecast_accuracy=.2),scenario_calibration=N(calibration_score=.2),thesis_validation=thesis,decision_quality_score=.2,decision_quality_grade='F',outcome_status='LOSS',positive_factors=(),warnings=('Warning',),remediation_actions=('Fix',))
    r=ResearchDashboardEngine().build(dashboard_id='D',research_case=case,scenario_comparison=comp,decision_journal=journal,outcome_attribution=attr,thesis_validation=N(case_id='C',thesis_validation=thesis))
    assert r.phase_completion.phase_status=='INCOMPLETE'; assert not r.scorecard.institutional_ready; assert r.phase_completion.consistency_errors
    print('Milestone 34 Phase 4 completion-governance assertions passed.')
if __name__=='__main__': main()
