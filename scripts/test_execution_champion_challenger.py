from dataclasses import asdict

from trading_ai.strategy_engine.execution_champion_challenger_engine import ExecutionChampionChallengerEngine
from trading_ai.strategy_engine.execution_champion_challenger_serialization import execution_champion_challenger_to_dict
from trading_ai.strategy_engine.execution_champion_challenger_service import ExecutionChampionChallengerService


def route(version, name, **overrides):
    payload = {
        "version": version,
        "route_type": "VENUE",
        "route_name": name,
        "observation_count": 250,
        "route_score": 72.0,
        "confidence_score": 78.0,
        "average_shortfall_bps": 8.0,
        "average_fill_ratio": 0.94,
        "average_latency_seconds": 4.0,
        "average_spread_bps": 5.0,
        "average_market_impact_bps": 3.5,
        "average_effective_spread_bps": 4.5,
        "governance_score": 82.0,
        "governance_allowed": True,
        "governance_severity": "LOW",
    }
    payload.update(overrides)
    return payload


def main():
    champion = route("venue-1.0", "SMART")
    challenger = route(
        "venue-1.1", "SMART_V2",
        route_score=79.0,
        confidence_score=86.0,
        average_shortfall_bps=5.5,
        average_fill_ratio=0.97,
        average_latency_seconds=3.0,
        average_spread_bps=4.0,
        average_market_impact_bps=2.4,
        average_effective_spread_bps=3.7,
        governance_score=88.0,
    )
    engine = ExecutionChampionChallengerEngine()
    profile = engine.evaluate(champion, challenger)
    assert profile.valid
    assert profile.allowed
    assert profile.recommendation == "PROMOTE_CHALLENGER"
    assert profile.route_score_improvement == 7.0
    assert profile.shortfall_improvement_bps == 2.5
    assert profile.evaluation_score >= 65.0
    assert len(profile.metric_comparisons) == 8

    rejected = engine.evaluate(champion, route(
        "venue-1.2", "WEAK",
        observation_count=10,
        route_score=60.0,
        confidence_score=40.0,
        average_shortfall_bps=12.0,
        average_fill_ratio=0.80,
        governance_score=45.0,
        governance_allowed=False,
        governance_severity="SEVERE",
    ))
    assert rejected.valid
    assert not rejected.allowed
    assert rejected.recommendation == "HOLD_CHAMPION"
    assert "INSUFFICIENT_CHALLENGER_OBSERVATIONS" in rejected.rejection_reasons
    assert "CHALLENGER_GOVERNANCE_REJECTED" in rejected.rejection_reasons

    batch = engine.evaluate_batch(champion, [challenger, route("venue-1.3", "SECOND", route_score=75.0, average_shortfall_bps=7.0)])
    assert batch.valid
    assert batch.challenger_count == 2
    assert batch.best_challenger_version == "venue-1.1"

    payload = execution_champion_challenger_to_dict(profile)
    assert payload["allowed"] is True
    assert isinstance(payload["metric_comparisons"], list)
    assert asdict(profile)["challenger_version"] == "venue-1.1"

    service = ExecutionChampionChallengerService()
    assert service.evaluate(champion, challenger).allowed

    print("All execution champion-challenger governance assertions passed.")


if __name__ == "__main__":
    main()
