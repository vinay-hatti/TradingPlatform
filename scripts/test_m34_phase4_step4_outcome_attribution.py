from types import SimpleNamespace as N
from trading_ai.research_workstation.outcome_attribution import OutcomeAttributionEngine,outcome_attribution_payload
def main():
 rc=N(case_id="CASE-1",symbol="AAPL",strategy_name="BULL_PUT_SPREAD",scenarios=(N(scenario_id="BULL",probability=.7,expected_return_pct=.15,expected_volatility_pct=.25,expected_drawdown_pct=.05),),evidence=(N(reliability_score=.9),)); sc=N(best_scenario_id="BULL"); dj=N(journal_id="J-1",decision_status="APPROVED_FOR_EXECUTION",decision_confidence=.8)
 r=OutcomeAttributionEngine().evaluate(attribution_id="ATTR-1",research_case=rc,scenario_comparison=sc,decision_journal=dj,realized_outcome={"realized_return_pct":.14,"realized_volatility_pct":.27,"realized_drawdown_pct":.04,"holding_period_days":18,"exit_reason":"Profit target","realized_scenario_id":"BULL","pnl_amount":1400,"realized_catalysts":["Guidance"],"valid_assumptions":["Stable"],"invalid_assumptions":[],"invalidation_triggers":[]})
 assert r.outcome_status=="PROFITABLE" and r.scenario_calibration["scenario_match"] and r.thesis_validation["validation_status"]=="CONFIRMED" and not r.rejection_reasons; assert outcome_attribution_payload(r)["attribution_id"]=="ATTR-1"; print("All Milestone 34 Phase 4 Step 4 outcome-attribution assertions passed.")
if __name__=="__main__": main()
