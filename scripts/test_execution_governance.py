import json
from types import SimpleNamespace

from trading_ai.strategy_engine.execution_governance_policy import ExecutionGovernancePolicy
from trading_ai.strategy_engine.execution_governance_serialization import execution_governance_to_dict
from trading_ai.strategy_engine.execution_governance_service import ExecutionGovernanceService


def build_rows(count, *, shortfall=8.0, latency=2.0, fill_ratio=0.99, score=90.0, spread=6.0):
    rows = []
    for index in range(count):
        venue = "CBOE" if index % 2 == 0 else "ISE"
        broker = "BROKER_A" if index % 2 == 0 else "BROKER_B"
        noise = ((index % 9) - 4) * 0.15
        rows.append({
            "order_id": f"O{index}",
            "venue": venue,
            "broker": broker,
            "implementation_shortfall_bps": shortfall + noise,
            "arrival_slippage_bps": shortfall * 0.70 + noise,
            "market_impact_bps": shortfall * 0.40 + noise,
            "effective_spread_bps": spread + noise,
            "fill_ratio": max(0.0, min(1.0, fill_ratio - abs(noise) * 0.001)),
            "fill_delay_seconds": latency + abs(noise),
            "execution_score": score - abs(noise),
        })
    return rows


def main():
    policy = ExecutionGovernancePolicy(
        minimum_baseline_observations=80,
        minimum_current_observations=40,
        minimum_segment_observations=15,
    )
    service = ExecutionGovernanceService(policy)

    baseline = build_rows(120)
    stable = build_rows(80, shortfall=8.0, latency=2.0, fill_ratio=0.99, score=90.0)
    profile = service.analyze(baseline, stable, baseline_name="Q1", current_name="Q2")
    assert profile.valid is True
    assert profile.allowed is True
    assert profile.metric_count == 7
    assert profile.segment_count == 4
    assert profile.governance_grade in {"A", "B", "C", "D", "F"}
    assert profile.drift_severity in {"LOW", "MODERATE", "SEVERE", "CRITICAL"}
    assert profile.recommendation in {"RETAIN_ACTIVE_ROUTES", "REVIEW_EXECUTION_DRIFT"}
    assert all(item.valid for item in profile.metric_profiles)
    assert {item.segment_type for item in profile.segment_profiles} == {"VENUE", "BROKER"}
    json.dumps(execution_governance_to_dict(profile))

    degraded = build_rows(80, shortfall=50.0, latency=15.0, fill_ratio=0.75, score=45.0, spread=30.0)
    critical = service.analyze(baseline, degraded)
    assert critical.valid is True
    assert critical.allowed is False
    assert critical.drift_severity in {"SEVERE", "CRITICAL"}
    assert critical.rejection_reasons
    assert critical.deteriorated_metric_count >= 4
    assert critical.recommendation == "RESTRICT_OR_REVIEW_ROUTES"

    target = SimpleNamespace(metadata={})
    service.attach([target], profile)
    assert target.execution_governance_profile is profile
    assert target.execution_governance_valid is True
    assert target.metadata["execution_governance_profile"] is profile

    empty = service.analyze([], [])
    assert empty.valid is False
    assert empty.allowed is True
    assert "NO_VALID_EXECUTION_GOVERNANCE_METRICS" in empty.warnings

    strict = ExecutionGovernanceService(ExecutionGovernancePolicy(
        minimum_baseline_observations=100,
        minimum_current_observations=50,
        allow_insufficient_data=False,
    )).analyze(build_rows(10), build_rows(10))
    assert strict.allowed is False
    assert "INSUFFICIENT_BASELINE_OBSERVATIONS" in strict.rejection_reasons

    print("All execution-governance foundation assertions passed.")


if __name__ == "__main__":
    main()
