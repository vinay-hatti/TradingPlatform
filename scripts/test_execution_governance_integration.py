from types import SimpleNamespace

from trading_ai.strategy_engine.execution_governance_integration_policy import ExecutionGovernanceIntegrationPolicy
from trading_ai.strategy_engine.execution_governance_integration_serialization import execution_governance_integration_to_dict
from trading_ai.strategy_engine.execution_governance_integration_service import ExecutionGovernanceIntegrationService


def decision():
    return SimpleNamespace(allowed=True, warnings=[], rejection_reasons=[], metadata={})


def main():
    governance = SimpleNamespace(
        valid=True, allowed=True, governance_score=91.0, governance_grade="A",
        drift_severity="LOW", aggregate_psi=0.03, maximum_metric_psi=0.07,
        deteriorated_metric_count=0, recommendation="MAINTAIN_ROUTE",
        warnings=(), rejection_reasons=(),
    )
    registry = SimpleNamespace(
        valid=True, route_count=2, active_version="venue-v1", champion_version="venue-v1",
        challenger_versions=("venue-v2",),
    )
    comparison = SimpleNamespace(
        valid=True, allowed=True, challenger_version="venue-v2", evaluation_score=88.0,
        recommendation="PROMOTE_CHALLENGER", warnings=(), rejection_reasons=(),
    )
    service = ExecutionGovernanceIntegrationService()
    profile = service.analyze(
        governance_profile=governance, route_registry_profile=registry,
        champion_challenger_profile=comparison,
    )
    assert profile.valid and profile.allowed
    assert profile.route_promotion_recommended
    item = decision(); service.attach([item], profile)
    assert item.execution_governance_score == 91.0
    assert item.execution_champion_route_version == "venue-v1"
    assert item.execution_route_promotion_recommended
    payload = execution_governance_integration_to_dict(profile)
    assert payload["governance_grade"] == "A"

    bad = SimpleNamespace(
        valid=True, allowed=False, governance_score=20.0, governance_grade="F",
        drift_severity="CRITICAL", aggregate_psi=0.9, maximum_metric_psi=1.1,
        deteriorated_metric_count=5, recommendation="SUSPEND_ROUTE",
        warnings=("DRIFT",), rejection_reasons=("CRITICAL_DRIFT",),
    )
    strict = ExecutionGovernanceIntegrationService(ExecutionGovernanceIntegrationPolicy())
    blocked = strict.analyze(governance_profile=bad, route_registry_profile=registry)
    assert not blocked.allowed
    item = decision(); strict.attach([item], blocked)
    assert not item.allowed and "CRITICAL_DRIFT" in item.rejection_reasons
    print("All execution governance integration assertions passed.")


if __name__ == "__main__":
    main()
