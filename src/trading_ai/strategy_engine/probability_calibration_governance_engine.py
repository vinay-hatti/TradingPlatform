from __future__ import annotations
import numpy as np
from trading_ai.strategy_engine.probability_calibration_engine import ProbabilityCalibrationEngine
from trading_ai.strategy_engine.probability_calibration_governance_policy import ProbabilityCalibrationGovernancePolicy
from trading_ai.strategy_engine.probability_calibration_governance_profile import CalibrationModelEvaluation, ProbabilityCalibrationGovernanceProfile

class ProbabilityCalibrationGovernanceEngine:
    def __init__(self, policy=None, calibration_engine=None):
        self.policy=(policy or ProbabilityCalibrationGovernancePolicy()).validate(); self.calibration_engine=calibration_engine or ProbabilityCalibrationEngine()
    def evaluate(self, champion_profile, challenger_profile, probabilities, outcomes, *, champion_version='CHAMPION', challenger_version='CHALLENGER', drift_profile=None):
        p=np.asarray(list(probabilities),dtype=float); y=np.asarray(list(outcomes),dtype=float)
        if len(p)!=len(y): raise ValueError('probabilities and outcomes must have equal length')
        warnings=[]; rejects=[]
        if len(p)<self.policy.minimum_evaluation_observations: rejects.append('INSUFFICIENT_GOVERNANCE_EVALUATION_OBSERVATIONS')
        ce=self._eval(champion_profile,p,y,champion_version); xe=self._eval(challenger_profile,p,y,challenger_version)
        bi=ce.brier_score-xe.brier_score; li=ce.log_loss-xe.log_loss; ed=xe.expected_calibration_error-ce.expected_calibration_error
        eligible=(not rejects and bi>=self.policy.minimum_brier_improvement and li>=self.policy.minimum_log_loss_improvement and ed<=self.policy.maximum_ece_deterioration and xe.calibration_score>=self.policy.minimum_challenger_score and (xe.allowed or not self.policy.require_challenger_allowed))
        if drift_profile is not None and self.policy.reject_critical_drift and getattr(drift_profile,'drift_severity','UNKNOWN')=='CRITICAL': eligible=False; rejects.append('CHALLENGER_CRITICAL_DRIFT')
        recommendation='PROMOTE_CHALLENGER' if eligible else 'RETAIN_CHAMPION'
        if not eligible: warnings.append('CHALLENGER_PROMOTION_CRITERIA_NOT_MET')
        confidence=max(0,min(100,50+bi*1000+li*500-ed*300))
        grade='A' if confidence>=85 else 'B' if confidence>=75 else 'C' if confidence>=65 else 'D' if confidence>=50 else 'F'
        severity='LOW' if eligible else ('SEVERE' if rejects else 'MODERATE')
        return ProbabilityCalibrationGovernanceProfile(champion_version,challenger_version,ce,xe,bi,li,ed,recommendation,eligible,False,confidence,grade,severity,not bool(rejects),not bool(rejects),drift_profile,warnings,rejects,{'evaluation_observations':len(p)})
    def _eval(self,profile,p,y,version):
        q=self.calibration_engine.calibrate_many(profile,p)
        b=float(np.mean((q-y)**2)); ll=float(-np.mean(y*np.log(np.clip(q,1e-6,1-1e-6))+(1-y)*np.log(np.clip(1-q,1e-6,1-1e-6))))
        errors=[]; counts=[]
        for lo,hi in zip(np.linspace(0,1,11)[:-1],np.linspace(0,1,11)[1:]):
            m=(q>=lo)&((q<hi) if hi<1 else q<=hi)
            if np.any(m): errors.append(abs(float(np.mean(q[m])-np.mean(y[m])))); counts.append(int(np.sum(m)))
        ece=sum(e*c for e,c in zip(errors,counts))/len(q) if len(q) else 0
        return CalibrationModelEvaluation(version,b,ll,ece,float(getattr(profile,'calibration_score',0)),bool(getattr(profile,'allowed',False)))
