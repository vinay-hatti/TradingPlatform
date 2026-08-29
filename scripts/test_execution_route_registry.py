from pathlib import Path
import json
import tempfile

from trading_ai.strategy_engine.execution_route_registry_service import ExecutionRouteRegistryService
from trading_ai.strategy_engine.execution_route_registry_serialization import execution_route_registry_to_dict


def route(name, score, shortfall, fill, latency, spread, observations=150, governance=90.0):
    return {
        "route_type": "VENUE",
        "route_name": name,
        "observation_count": observations,
        "route_score": score,
        "confidence_score": 90.0,
        "average_shortfall_bps": shortfall,
        "average_fill_ratio": fill,
        "average_latency_seconds": latency,
        "average_spread_bps": spread,
        "governance_score": governance,
        "governance_grade": "A",
        "governance_severity": "LOW",
        "governance_allowed": True,
    }


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "route_registry.json"
        service = ExecutionRouteRegistryService(path)
        service.register_route("venue-v1", route("CBOE", 75.0, 10.0, 0.95, 2.0, 5.0), activate=True, champion=True)
        service.register_route("venue-v2", route("ISE", 84.0, 6.0, 0.97, 1.5, 4.0), challenger=True)

        evaluation = service.evaluate_challenger("venue-v2")
        assert evaluation.valid
        assert evaluation.allowed
        assert evaluation.recommendation == "PROMOTE_CHALLENGER"
        assert evaluation.route_score_improvement == 9.0

        promoted = service.promote_challenger("venue-v2", actor="REGRESSION_TEST")
        assert promoted.promoted
        assert service.registry.champion()["version"] == "venue-v2"
        assert service.registry.active()["version"] == "venue-v2"

        service.register_route("venue-v3", route("BAD", 78.0, 18.0, 0.88, 7.0, 10.0, observations=20, governance=45.0), challenger=True)
        rejected = service.evaluate_challenger("venue-v3")
        assert rejected.valid
        assert not rejected.allowed
        assert rejected.rejection_reasons

        profile = service.profile()
        assert profile.valid
        assert profile.route_count == 3
        assert profile.champion_version == "venue-v2"
        assert profile.audit_event_count >= 7

        payload = execution_route_registry_to_dict(profile)
        json.dumps(payload)
        assert path.exists()

        reloaded = ExecutionRouteRegistryService(path)
        assert reloaded.registry.champion()["version"] == "venue-v2"
        assert len(reloaded.registry.audit_log()) == profile.audit_event_count

    print("All execution route registry assertions passed.")


if __name__ == "__main__":
    main()
