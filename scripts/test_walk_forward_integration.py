from types import SimpleNamespace
from trading_ai.strategy_engine.walk_forward_integration_policy import WalkForwardIntegrationPolicy
from trading_ai.strategy_engine.walk_forward_integration_service import WalkForwardIntegrationService
from trading_ai.strategy_engine.decision_run_result import DecisionRunResult


def main():
    raw = SimpleNamespace(
        valid=True, allowed=True, window_count=6, completed_window_count=6,
        aggregate_oos_return=0.18, average_oos_sharpe=1.15,
        worst_oos_drawdown_pct=0.12, average_degradation_pct=0.08,
        parameter_stability_score=78.0, window_consistency_score=83.0,
        walk_forward_score=81.0, walk_forward_grade="A", risk_severity="LOW",
        results=[], warnings=[], rejection_reasons=[],
    )
    service = WalkForwardIntegrationService(WalkForwardIntegrationPolicy())
    profile = service.evaluate(raw)
    assert profile.valid and profile.allowed
    decision = SimpleNamespace(
        allowed=True, metadata={}, warnings=[], rejection_reasons=[]
    )
    service.attach([decision], profile)
    assert decision.walk_forward_validated is True
    assert decision.walk_forward_score == 81.0
    assert decision.metadata["walk_forward_profile"] is profile

    result = DecisionRunResult(
        decisions=[], selected_decisions=[], rejected_decisions=[],
        candidate_bundles=[], ranked_opportunities=[], portfolio_result=None,
        symbol_diagnostics=[], total_symbols=0, processed_symbols=0,
        total_candidates=0, accepted_candidates=0, rejected_candidates=0,
        selected_count=0, overall_readiness="RESEARCH_ONLY",
        overall_action="NO_ACTION", valid=True,
        walk_forward_profile=profile,
    )
    assert result.walk_forward_profile.walk_forward_grade == "A"

    strict = WalkForwardIntegrationService(WalkForwardIntegrationPolicy(
        reject_critical_severity=True,
    ))
    bad = SimpleNamespace(**{**raw.__dict__, "risk_severity": "CRITICAL"})
    bad_profile = strict.evaluate(bad)
    assert not bad_profile.allowed
    print("All walk-forward integration assertions passed.")


if __name__ == "__main__":
    main()
