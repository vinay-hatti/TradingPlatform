from types import SimpleNamespace
from trading_ai.research_workstation.pattern_discovery import PatternDiscoveryEngine

def case(cid,symbol,sector,strategy,outcome,thesis,score,tags):
    return SimpleNamespace(case_id=cid,symbol=symbol,sector=sector,strategy_name=strategy,outcome_status=outcome,thesis_validation_status=thesis,institutional_score=score,tags=tuple(SimpleNamespace(tag=t) for t in tags))
def main():
    cases=(case("C1","AAPL","Technology","BULL_PUT_SPREAD","PROFITABLE","CONFIRMED",.84,("technology","earnings","bullish")),case("C2","MSFT","Technology","BULL_PUT_SPREAD","PROFITABLE","CONFIRMED",.82,("technology","earnings","bullish")),case("C3","XOM","Energy","LONG_CALL","LOSS","INVALIDATED",.44,("energy","oil","bullish")))
    engine=PatternDiscoveryEngine(); score,shared,dims=engine.similarity_score(cases[0],cases[1])
    assert score>=.75 and "STRATEGY" in dims and "SECTOR" in dims and "earnings" in shared
    report=engine.build_similarity_report(knowledge_base=SimpleNamespace(cases=cases))
    assert report.governance_status=="READY" and report.match_count>=1 and report.matches[0].similarity_band=="HIGH"
    print("Milestone 34 Phase 5 Step 2 similarity assertions passed.")
if __name__=="__main__": main()
