from __future__ import annotations
from .service import PortfolioRiskAllocationService
from .decision_intelligence import InstitutionalDecisionIntelligenceService
from .optimizer import PortfolioOptimizationService

class Milestone64ContinuousPortfolioIntelligenceService:
    """Single operational entry point for the complete Milestone 64 cycle."""
    def __init__(self, session_factory):
        self.session_factory=session_factory
    def run(self, portfolio_id='PAPER-PRIMARY', actor='m64-continuous-intelligence'):
        risk=PortfolioRiskAllocationService(self.session_factory).build(portfolio_id,actor)
        decisions=InstitutionalDecisionIntelligenceService(self.session_factory).build(portfolio_id)
        optimization=PortfolioOptimizationService(self.session_factory).build(
            portfolio_id,rebuild_decisions=False,actor=actor
        )
        return {
            'portfolio_id':portfolio_id,
            'risk_snapshot_id':risk['snapshot_id'],
            'decision_count':decisions['built'],
            'optimization_snapshot_id':optimization['optimization_snapshot_id'],
            'selected_count':len(optimization['selected_candidates']),
            'action_count':len(optimization['recommended_actions']),
            'status':optimization['status'],
        }
