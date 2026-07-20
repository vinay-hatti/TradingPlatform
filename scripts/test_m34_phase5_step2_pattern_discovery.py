from types import SimpleNamespace
from trading_ai.research_workstation.pattern_discovery import PatternDiscoveryEngine

def case(cid,sector,strategy,outcome,thesis,score,tags):
    return SimpleNamespace(case_id=cid,symbol=cid,sector=sector,strategy_name=strategy,outcome_status=outcome,thesis_validation_status=thesis,institutional_score=score,tags=tuple(SimpleNamespace(tag=t) for t in tags))
def main():
    kb=SimpleNamespace(cases=(case("C1","Technology","BULL_PUT_SPREAD","PROFITABLE","CONFIRMED",.84,("technology","bullish")),case("C2","Technology","BULL_PUT_SPREAD","PROFITABLE","CONFIRMED",.82,("technology","bullish")),case("C3","Energy","LONG_CALL","LOSS","INVALIDATED",.44,("energy","bullish"))))
    result=PatternDiscoveryEngine().build_pattern_discovery(knowledge_base=kb)
    assert result.governance_status=="READY" and result.cluster_count>=4
    assert any(c.cluster_type=="SECTOR" and c.cluster_key=="Technology" for c in result.clusters)
    assert result.strongest_patterns
    print("Milestone 34 Phase 5 Step 2 pattern-discovery assertions passed.")
if __name__=="__main__": main()
