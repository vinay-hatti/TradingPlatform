from datetime import datetime,timezone
from typing import Any,Mapping
from .outcome_attribution_policy import OutcomeAttributionPolicy
from .outcome_attribution_profile import OutcomeAttributionProfile
class OutcomeAttributionEngine:
    def __init__(self,policy=None): self.policy=policy or OutcomeAttributionPolicy(); self.policy.validate()
    @staticmethod
    def _get(x,n,d=None): return x.get(n,d) if isinstance(x,Mapping) else getattr(x,n,d)
    @staticmethod
    def _grade(s): return "A" if s>=.9 else "B" if s>=.8 else "C" if s>=.7 else "D" if s>=.6 else "F"
    def evaluate(self,*,attribution_id,research_case,scenario_comparison,decision_journal,realized_outcome,metadata=None):
        scenarios=tuple(self._get(research_case,"scenarios",()) or ())
        sid=self._get(scenario_comparison,"best_scenario_id",None)
        selected=next((s for s in scenarios if str(self._get(s,"scenario_id",""))==str(sid)),scenarios[0] if scenarios else {})
        er=float(self._get(selected,"expected_return_pct",0)); ev=float(self._get(selected,"expected_volatility_pct",0)); ed=float(self._get(selected,"expected_drawdown_pct",0)); p=float(self._get(selected,"probability",0))
        rr=float(realized_outcome.get("realized_return_pct",0)); rv=float(realized_outcome.get("realized_volatility_pct",0)); rd=float(realized_outcome.get("realized_drawdown_pct",0)); rsid=realized_outcome.get("realized_scenario_id")
        complete=sum(k in realized_outcome and realized_outcome.get(k) not in (None,"") for k in ("realized_return_pct","realized_volatility_pct","realized_drawdown_pct","holding_period_days","exit_reason","realized_scenario_id","pnl_amount"))/7
        direction=float((er>0)==(rr>0))
        re,ve,de=abs(rr-er),abs(rv-ev),abs(rd-ed)
        match=str(sid)==str(rsid); pe=abs(p-(1.0 if match else 0.0)); brier=pe**2
        confidence=float(self._get(decision_journal,"decision_confidence",0)); ce=abs(confidence-(1.0 if rr>0 else 0.0))
        fa=max(0,min(1,(direction+(1-min(1,re/.10))+(1-min(1,ve/.10))+(1-min(1,de/.10))+(1-min(1,pe/.20))+(1-min(1,ce)))/6))
        cal=max(0,min(1,((1 if match else 0)+(1-min(1,pe))+(1-min(1,brier)))/3))
        inval=tuple(realized_outcome.get("invalidation_triggers",()) or ())
        valid=tuple(realized_outcome.get("valid_assumptions",()) or ()); invalid=tuple(realized_outcome.get("invalid_assumptions",()) or ())
        ass=len(valid)/(len(valid)+len(invalid)) if valid or invalid else .5
        evid=tuple(self._get(research_case,"evidence",()) or ()); eq=sum(float(self._get(e,"reliability_score",0)) for e in evid)/len(evid) if evid else 0
        cat=1.0 if realized_outcome.get("realized_catalysts") else .5
        align=1-min(1,re/.10); confirm=max(0,min(1,(cat+ass+eq+align+(0 if inval else 1))/5))
        status="INVALIDATED" if inval or confirm<self.policy.minimum_partial_confirmation_score else "CONFIRMED" if confirm>=self.policy.minimum_thesis_confirmation_score else "PARTIALLY_CONFIRMED"
        dq=max(0,min(1,(fa+cal+confirm+(1 if self._get(decision_journal,"decision_status","") else .5)+complete)/5))
        outcome="PROFITABLE" if rr>.03 else "LOSS" if rr<-.03 else "FLAT"
        warnings=[]; rejects=[]; remed=[]; positives=[]
        if complete<self.policy.minimum_data_completeness: rejects.append("Realized outcome data completeness is below policy."); remed.append("Supply all required realized outcome fields.")
        else: positives.append("Realized outcome data meets completeness policy")
        if dq<self.policy.minimum_decision_quality_score: warnings.append("Decision quality score is below policy threshold."); remed.append("Review research, calibration, and risk controls.")
        if status=="INVALIDATED": warnings.append("Research thesis was invalidated.")
        factors=(
          {"factor_name":"directional_call","category":"FORECAST","contribution_score":1 if direction else -1,"favorable":bool(direction)},
          {"factor_name":"scenario_selection","category":"SCENARIO","contribution_score":1 if match else -.75,"favorable":match},
          {"factor_name":"risk_control","category":"RISK","contribution_score":1 if rd<=ed else -1,"favorable":rd<=ed},
        )
        feedback={"strengths":tuple(x for x in ("Directional forecast was accurate." if direction else "", "Scenario selection was accurate." if match else "") if x),"weaknesses":tuple(x for x in ("Directional forecast was inaccurate." if not direction else "", "Scenario selection missed realized regime." if not match else "") if x),"recommendations":tuple(x for x in ("Review directional evidence weighting." if not direction else "", "Improve scenario probability calibration." if not match else "") if x),"lessons":({"lesson_id":f"{attribution_id}-LESSON-001","category":"FORECAST","lesson":"Forecast aligned with outcome." if direction else "Forecast missed outcome."},)}
        return OutcomeAttributionProfile(attribution_id,str(self._get(research_case,"case_id","UNKNOWN")),str(self._get(decision_journal,"journal_id","UNKNOWN")),str(self._get(research_case,"symbol","UNKNOWN")),str(self._get(research_case,"strategy_name","UNKNOWN")),datetime.now(timezone.utc),round(er,6),round(rr,6),round(ev,6),round(rv,6),round(ed,6),round(rd,6),int(realized_outcome.get("holding_period_days",0)),str(realized_outcome.get("exit_reason","")),round(float(realized_outcome.get("pnl_amount",0)),2),outcome,round(complete,6),{"directional_accuracy":direction,"return_error_pct":round(re,6),"volatility_error_pct":round(ve,6),"drawdown_error_pct":round(de,6),"probability_error":round(pe,6),"brier_score":round(brier,6),"confidence_calibration_error":round(ce,6),"overall_forecast_accuracy":round(fa,6),"forecast_grade":self._grade(fa)},{"selected_scenario_id":sid,"realized_scenario_id":rsid,"selected_scenario_probability":round(p,6),"scenario_match":match,"calibration_score":round(cal,6),"calibration_grade":self._grade(cal)},{"validation_status":status,"confirmation_score":round(confirm,6),"assumption_validity_score":round(ass,6),"evidence_quality_score":round(eq,6),"invalidation_triggered":bool(inval),"invalidation_reasons":inval},factors,feedback,round(dq,6),self._grade(dq),tuple(positives),tuple(warnings),tuple(rejects),tuple(remed),{"milestone":34,"phase":4,"step":4,**dict(metadata or {})})
