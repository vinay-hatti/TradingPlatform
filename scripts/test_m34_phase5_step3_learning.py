from types import SimpleNamespace
from trading_ai.research_workstation.institutional_learning import InstitutionalLearningEngine

def c(i,strategy,sector,outcome,thesis,score,tags): return SimpleNamespace(case_id=i,strategy_name=strategy,sector=sector,outcome_status=outcome,thesis_validation_status=thesis,institutional_score=score,predicted_probability=score,tags=tuple(SimpleNamespace(tag=t) for t in tags))
def main():
    kb=SimpleNamespace(cases=(c("C1","BULL_PUT_SPREAD","Technology","PROFITABLE","CONFIRMED",.8,("earnings","bullish")),c("C2","BULL_PUT_SPREAD","Technology","PROFITABLE","CONFIRMED",.75,("earnings","bullish")),c("C3","LONG_CALL","Energy","LOSS","INVALIDATED",.7,("oil","bullish"))))
    r=InstitutionalLearningEngine().build(knowledge_base=kb)
    assert r.governance_status=="READY"; assert r.summary.total_cases==3; assert r.strategy_learning; assert r.sector_learning; assert r.recommendations; assert 0<=r.summary.brier_score<=1
    print("Milestone 34 Phase 5 Step 3 learning assertions passed.")
if __name__=="__main__": main()
