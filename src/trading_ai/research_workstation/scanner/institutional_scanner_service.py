from __future__ import annotations
from dataclasses import replace
from .institutional_decision_adapter import InstitutionalDecisionEngineAdapter
from .institutional_request_factory import InstitutionalDecisionInputBundle,InstitutionalDecisionRequestFactory
from .institutional_scanner_policy import InstitutionalScannerFilterPolicy
from .institutional_scoring_engine import InstitutionalScannerScoringEngine
class InstitutionalScannerDecisionService:
    def __init__(self,*,adapter=None,request_factory=None,scoring_engine=None,filter_policy=None):
        self.adapter=adapter or InstitutionalDecisionEngineAdapter(); self.request_factory=request_factory or InstitutionalDecisionRequestFactory(); self.scoring_engine=scoring_engine or InstitutionalScannerScoringEngine(); self.filter_policy=filter_policy or InstitutionalScannerFilterPolicy()
    def _passes(self,p):
        f=self.filter_policy; return p.probability_of_profit>=f.minimum_probability_of_profit and p.expected_return>=f.minimum_expected_return and p.reward_risk_ratio>=f.minimum_reward_risk_ratio and p.decision_confidence>=f.minimum_decision_confidence and (p.allowed or not f.require_allowed) and (p.selected or not f.require_selected)
    def enrich(self,*,candidates,inputs:InstitutionalDecisionInputBundle,target_dte=30,initial_capital=100000.0,construct_portfolio=False,include_rejected=True):
        request=self.request_factory.build(candidates=candidates,inputs=inputs,target_dte=target_dte,initial_capital=initial_capital,construct_portfolio=construct_portfolio,include_rejected=include_rejected); run=self.adapter.run(request); out=[]
        for c in candidates:
            p=run.decisions_by_symbol.get(c.symbol.upper())
            if p is None or not self._passes(p): continue
            score=self.scoring_engine.score(p); metadata=dict(c.metadata); metadata['institutional_decision']={'available':p.available,'allowed':p.allowed,'selected':p.selected,'action':p.action,'readiness':p.readiness,'strategy':p.strategy,'probability_of_profit':p.probability_of_profit,'calibrated_probability':p.calibrated_probability,'institutional_score':score,'tail_risk_grade':p.tail_risk_grade,'recommended_position_size_pct':p.recommended_position_size_pct,'stop_loss_pct':p.stop_loss_pct,'take_profit_pct':p.take_profit_pct,'warnings':list(p.warnings),'rejection_reasons':list(p.rejection_reasons),**p.metadata}
            out.append(replace(c,decision_confidence=p.decision_confidence,expected_return=p.expected_return,risk_score=p.risk_score,reward_risk_ratio=p.reward_risk_ratio,metadata=metadata))
        return tuple(out),run
