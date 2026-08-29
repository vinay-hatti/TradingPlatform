from types import SimpleNamespace
from trading_ai.research_workstation.institutional_learning import InstitutionalLearningEngine

def main():
    cases=tuple(SimpleNamespace(case_id=f"C{i}",strategy_name="IRON_CONDOR",sector="Index",outcome_status="PROFITABLE" if i<4 else "LOSS",thesis_validation_status="CONFIRMED",institutional_score=.8,tags=(SimpleNamespace(tag="income"),)) for i in range(5))
    r=InstitutionalLearningEngine().build(knowledge_base=SimpleNamespace(cases=cases)); row=next(x for x in r.strategy_learning if x.factor_key=="IRON_CONDOR")
    assert row.occurrences==5; assert row.successes==4; assert row.posterior_success_probability>0.5; assert row.recommendation=="INCREASE_CONFIDENCE"
    print("Milestone 34 Phase 5 Step 3 strategy-learning assertions passed.")
if __name__=="__main__": main()
