from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Mapping
from .research_dashboard_policy import ResearchDashboardPolicy
from .research_dashboard_profile import (
    DashboardSectionProfile, ExecutiveSummaryProfile, KPIProfile,
    PhaseCompletionProfile, ResearchDashboardProfile, ResearchScorecardProfile,
)

class ResearchDashboardEngine:
    def __init__(self, policy: ResearchDashboardPolicy | None = None) -> None:
        self.policy=policy or ResearchDashboardPolicy(); self.policy.validate()

    @staticmethod
    def _get(src: Any, name: str, default: Any=None) -> Any:
        return src.get(name, default) if isinstance(src, Mapping) else getattr(src,name,default)

    @staticmethod
    def _clamp(v: float) -> float: return max(0.0,min(1.0,float(v)))

    @staticmethod
    def _grade(v: float) -> str:
        return "A" if v>=.9 else "B" if v>=.8 else "C" if v>=.7 else "D" if v>=.6 else "F"

    def build(self, *, dashboard_id: str, research_case: Any, scenario_comparison: Any,
              decision_journal: Any, outcome_attribution: Any, thesis_validation: Any,
              source_artifacts: Mapping[str,str] | None=None) -> ResearchDashboardProfile:
        case_id=str(self._get(research_case,'case_id','UNKNOWN'))
        journal_id=str(self._get(decision_journal,'journal_id','UNKNOWN'))
        symbol=str(self._get(research_case,'symbol','UNKNOWN'))
        strategy=str(self._get(research_case,'strategy_name','UNKNOWN'))
        recommendation=self._get(scenario_comparison,'recommendation',{})
        action=str(self._get(recommendation,'action','MONITOR')).upper()
        confidence=float(self._get(recommendation,'confidence',self._get(decision_journal,'decision_confidence',0.0)))
        forecast=self._get(outcome_attribution,'forecast_accuracy',{})
        scenario=self._get(outcome_attribution,'scenario_calibration',{})
        thesis=self._get(outcome_attribution,'thesis_validation',self._get(thesis_validation,'thesis_validation',{}))
        evidence=tuple(self._get(research_case,'evidence',()) or ())
        evidence_scores=[float(self._get(x,'reliability_score',0.0)) for x in evidence]
        evidence_quality=sum(evidence_scores)/len(evidence_scores) if evidence_scores else 0.0
        forecast_score=float(self._get(forecast,'overall_forecast_accuracy',0.0))
        scenario_score=float(self._get(scenario,'calibration_score',0.0))
        thesis_score=float(self._get(thesis,'confirmation_score',0.0))
        decision_quality=float(self._get(outcome_attribution,'decision_quality_score',0.0))
        approval=str(self._get(decision_journal,'approval_status','NOT_REVIEWED'))
        review_score=1.0 if approval=='APPROVED' else .5 if approval in {'PENDING_REVIEW','NOT_REVIEWED'} else 0.0
        risk_score=1.0 if self._get(decision_journal,'primary_risks',()) and self._get(decision_journal,'monitoring_plan',()) else .5
        outcome_status=str(self._get(outcome_attribution,'outcome_status','UNKNOWN'))
        outcome_score=1.0 if outcome_status=='PROFITABLE' else .5 if outcome_status=='FLAT' else 0.0
        research_quality=self._clamp((evidence_quality+confidence+thesis_score)/3)
        metrics=(
            ('Research Quality',research_quality,'Evidence, confidence, and thesis quality.'),
            ('Evidence Quality',evidence_quality,'Average source reliability.'),
            ('Forecast Accuracy',forecast_score,'Realized forecast performance.'),
            ('Decision Quality',decision_quality,'Aggregate decision quality.'),
            ('Scenario Calibration',scenario_score,'Scenario ranking and probability calibration.'),
            ('Thesis Confirmation',thesis_score,'Realized thesis confirmation.'),
            ('Review Governance',review_score,'Independent review completion.'),
            ('Risk Governance',risk_score,'Risk and monitoring documentation.'),
            ('Outcome Quality',outcome_score,'Realized outcome quality.'),
        )
        kpis=tuple(KPIProfile(n,round(s,6),self._grade(s),'PASS' if s>=.6 else 'ATTENTION',e) for n,s,e in metrics)
        overall=self._clamp(sum(k.score for k in kpis)/len(kpis))
        present=tuple(k for k,v in {
            'research_case':research_case,'scenario_comparison':scenario_comparison,
            'decision_journal':decision_journal,'outcome_attribution':outcome_attribution,
            'thesis_validation':thesis_validation}.items() if v is not None)
        missing=tuple(x for x in self.policy.required_artifacts if x not in present)
        errors=[]
        if self.policy.require_consistent_case_ids:
            for label,obj in (('decision_journal',decision_journal),('outcome_attribution',outcome_attribution),('thesis_validation',thesis_validation)):
                oid=self._get(obj,'case_id',case_id)
                if oid not in (None,'',case_id): errors.append(f'{label} case_id does not match research case.')
        if self.policy.require_consistent_journal_link:
            linked=self._get(outcome_attribution,'journal_id',journal_id)
            if linked not in (None,'',journal_id): errors.append('Outcome attribution journal_id does not match decision journal.')
        completeness=len(present)/len(self.policy.required_artifacts)
        ready=(completeness>=self.policy.minimum_completeness_score and overall>=self.policy.minimum_institutional_score and not errors)
        status='COMPLETE' if ready else 'INCOMPLETE'
        positives=tuple(self._get(outcome_attribution,'positive_factors',()) or ())
        warnings=tuple(self._get(outcome_attribution,'warnings',()) or ())
        risks=tuple(self._get(decision_journal,'primary_risks',()) or ())
        actions=tuple(self._get(outcome_attribution,'remediation_actions',()) or ())
        conclusion=(f'{symbol} {strategy} research workflow is institutionally ready.' if ready else f'{symbol} {strategy} requires remediation before institutional closure.')
        executive=ExecutiveSummaryProfile(
            recommendation=action,research_status=status,
            confidence_summary=f'Recommendation confidence {confidence:.1%}; institutional score {overall:.1%}.',
            executive_conclusion=conclusion,key_strengths=positives,key_risks=risks or warnings,
            required_actions=actions,
        )
        sections=(
            DashboardSectionProfile('research-case','Research Case','COMPLETE',str(self._get(research_case,'primary_thesis','Research case loaded.')),{'case_id':case_id}),
            DashboardSectionProfile('scenario-comparison','Scenario Comparison','COMPLETE',f'Selected scenario: {self._get(scenario_comparison,"best_scenario_id","UNKNOWN")}.',{'recommendation':action,'confidence':confidence}),
            DashboardSectionProfile('decision-journal','Decision Journal',str(self._get(decision_journal,'decision_status','UNKNOWN')),str(self._get(decision_journal,'decision_rationale','')),{'approval_status':approval}),
            DashboardSectionProfile('outcome-attribution','Outcome Attribution',outcome_status,f'Decision quality grade: {self._get(outcome_attribution,"decision_quality_grade","N/A")}.',{'decision_quality_score':decision_quality}),
            DashboardSectionProfile('thesis-validation','Thesis Validation',str(self._get(thesis,'validation_status','UNKNOWN')),str(self._get(thesis,'thesis_summary','')),{'confirmation_score':thesis_score}),
        )
        return ResearchDashboardProfile(
            dashboard_id=dashboard_id,generated_at=datetime.now(timezone.utc),case_id=case_id,
            journal_id=journal_id,symbol=symbol,strategy_name=strategy,executive_summary=executive,
            scorecard=ResearchScorecardProfile(kpis,round(overall,6),self._grade(overall),ready),
            sections=sections,
            phase_completion=PhaseCompletionProfile(status,round(completeness,6),present,missing,tuple(errors),ready),
            source_artifacts=dict(source_artifacts or {}),warnings=warnings,
            metadata={'milestone':34,'phase':4,'step':5,'source':'RESEARCH_DASHBOARD_ENGINE'},
        )
