from trading_ai.scanner.market_data_quality.phase2_closure import *
def main():
    e=Phase2ClosureEngine()
    p=e.evaluate("READY","READY","DEGRADED","READY")
    assert p.overall_status is Phase2ClosureStatus.DEGRADED and p.production_approved
    p=e.evaluate("READY","FAILED","DEGRADED","READY")
    assert p.overall_status is Phase2ClosureStatus.FAILED and not p.production_approved
    print("Milestone 35 Phase 2 Step 5 phase closure assertions passed.")
if __name__=="__main__":main()
