from __future__ import annotations
import math
import numpy as np
from trading_ai.strategy_engine.probability_calibration_drift_policy import ProbabilityCalibrationDriftPolicy
from trading_ai.strategy_engine.probability_calibration_drift_profile import CalibrationWindowMetrics, ProbabilityCalibrationDriftProfile

class ProbabilityCalibrationDriftEngine:
    def __init__(self, policy=None):
        self.policy=(policy or ProbabilityCalibrationDriftPolicy()).validate()

    def analyze(self, reference_probabilities, reference_outcomes, recent_probabilities, recent_outcomes, *, model_version='UNVERSIONED', segment_key='GLOBAL'):
        rp=self._p(reference_probabilities); ry=self._y(reference_outcomes)
        np_=self._p(recent_probabilities); ny=self._y(recent_outcomes)
        if len(rp)!=len(ry) or len(np_)!=len(ny): raise ValueError('probability/outcome lengths must match')
        warnings=[]; rejects=[]
        if len(np_) < self.policy.minimum_recent_observations: rejects.append('INSUFFICIENT_RECENT_DRIFT_OBSERVATIONS')
        ref=self._metrics(rp,ry); recent=self._metrics(np_,ny)
        psi=self._psi(rp,np_)
        brier=recent.brier_score-ref.brier_score; log=recent.log_loss-ref.log_loss
        ece=recent.expected_calibration_error-ref.expected_calibration_error
        base=abs(recent.base_rate-ref.base_rate); mean=abs(recent.mean_probability-ref.mean_probability)
        severity=self._severity(brier,ece,psi,base)
        score=max(0.0,100.0-(max(0,brier)*250+max(0,ece)*200+psi*100+base*100))
        grade='A' if score>=85 else 'B' if score>=75 else 'C' if score>=65 else 'D' if score>=50 else 'F'
        if severity in {'MODERATE','SEVERE','CRITICAL'}: warnings.append(f'CALIBRATION_DRIFT_{severity}')
        allowed=not rejects and not(self.policy.reject_critical_drift and severity=='CRITICAL')
        if not allowed and severity=='CRITICAL': rejects.append('CRITICAL_PROBABILITY_CALIBRATION_DRIFT')
        return ProbabilityCalibrationDriftProfile(model_version,segment_key,ref,recent,brier,log,ece,base,mean,psi,score,grade,severity,allowed,not bool(rejects),warnings,rejects,{'metric_direction':'positive change indicates deterioration'})

    def _p(self,v): return np.clip(np.asarray(list(v),dtype=float),self.policy.probability_floor,self.policy.probability_ceiling)
    def _y(self,v):
        y=np.asarray(list(v),dtype=float)
        if np.any((y!=0)&(y!=1)): raise ValueError('outcomes must be binary')
        return y
    def _metrics(self,p,y):
        n=len(p)
        if n==0: return CalibrationWindowMetrics(0,0,0,0,0,0,0,0,0)
        b=float(np.mean((p-y)**2)); ll=float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p)))
        errors=[]; counts=[]
        for lo,hi in zip(np.linspace(0,1,self.policy.reliability_bins+1)[:-1],np.linspace(0,1,self.policy.reliability_bins+1)[1:]):
            mask=(p>=lo)&((p<hi) if hi<1 else (p<=hi))
            if np.any(mask): errors.append(abs(float(np.mean(p[mask])-np.mean(y[mask])))); counts.append(int(np.sum(mask)))
        ece=sum(e*c for e,c in zip(errors,counts))/n if n else 0
        return CalibrationWindowMetrics(n,int(np.sum(y)),int(n-np.sum(y)),float(np.mean(y)),b,ll,float(ece),max(errors,default=0.0),float(np.mean(p)))
    def _psi(self,a,b):
        edges=np.linspace(0,1,self.policy.probability_bins+1); ah,_=np.histogram(a,bins=edges); bh,_=np.histogram(b,bins=edges)
        ap=np.maximum(ah/max(len(a),1),1e-6); bp=np.maximum(bh/max(len(b),1),1e-6)
        return float(np.sum((bp-ap)*np.log(bp/ap)))
    def _severity(self,b,e,p,base):
        if b>=self.policy.critical_brier_increase or e>=self.policy.critical_ece_increase or p>=self.policy.critical_psi or base>=self.policy.critical_base_rate_shift: return 'CRITICAL'
        if b>=self.policy.severe_brier_increase or e>=self.policy.severe_ece_increase or p>=self.policy.severe_psi or base>=self.policy.severe_base_rate_shift: return 'SEVERE'
        if b>=self.policy.warning_brier_increase or e>=self.policy.warning_ece_increase or p>=self.policy.warning_psi or base>=self.policy.warning_base_rate_shift: return 'MODERATE'
        return 'LOW'
