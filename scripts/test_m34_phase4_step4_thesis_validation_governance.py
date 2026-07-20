from types import SimpleNamespace as N
from trading_ai.research_workstation.outcome_attribution import OutcomeAttributionEngine
def main():
 rc=N(case_id="CASE-L",symbol="RISK",strategy_name="LONG_CALL",scenarios=(N(scenario_id="BULL",probability=.85,expected_return_pct=.20,expected_volatility_pct=.22,expected_drawdown_pct=.05),),evidence=(N(reliability_score=.4),)); sc=N(best_scenario_id="BULL"); dj=N(journal_id="J-L",decision_status="APPROVED_FOR_EXECUTION",decision_confidence=.95)
 r=OutcomeAttributionEngine().evaluate(attribution_id="ATTR-L",research_case=rc,scenario_comparison=sc,decision_journal=dj,realized_outcome={"realized_return_pct":-.18,"realized_volatility_pct":.48,"realized_drawdown_pct":.24,"holding_period_days":7,"exit_reason":"Stop loss","realized_scenario_id":"BEAR","pnl_amount":-1800,"realized_catalysts":[],"valid_assumptions":[],"invalid_assumptions":["Breakout"],"invalidation_triggers":["Support failed"]})
 assert r.outcome_status=="LOSS" and not r.scenario_calibration["scenario_match"] and r.thesis_validation["validation_status"]=="INVALIDATED" and r.warnings and r.remediation_actions; print("Milestone 34 Phase 4 Step 4 thesis-validation governance assertions passed.")
if __name__=="__main__": main()
