import json
import tempfile
from pathlib import Path

from trading_ai.strategy_engine.walk_forward_governance_policy import WalkForwardGovernancePolicy
from trading_ai.strategy_engine.walk_forward_governance_service import WalkForwardGovernanceService
from trading_ai.strategy_engine.walk_forward_governance_serialization import walk_forward_governance_to_dict
from trading_ai.strategy_engine.walk_forward_parameter_registry import WalkForwardParameterRegistry
from trading_ai.strategy_engine.walk_forward_profile import WalkForwardProfile


def profile(score, ret, sharpe, drawdown, degradation, stability, severity="LOW"):
    return WalkForwardProfile(
        valid=True, allowed=True, window_count=6, completed_window_count=6,
        aggregate_oos_return=ret, average_oos_sharpe=sharpe,
        worst_oos_drawdown_pct=drawdown, average_degradation_pct=degradation,
        parameter_stability_score=stability, window_consistency_score=80.0,
        walk_forward_score=score, walk_forward_grade="B", risk_severity=severity,
    )


def main():
    champion = profile(68.0, 0.08, 0.72, -0.12, 0.06, 62.0)
    challenger = profile(76.0, 0.12, 0.95, -0.11, 0.05, 78.0)
    with tempfile.TemporaryDirectory() as tmp:
        registry = WalkForwardParameterRegistry(Path(tmp) / "registry.json")
        registry.register("v1", {"threshold": 0.60}, champion, activate=True)
        policy = WalkForwardGovernancePolicy(automatic_promotion_enabled=True)
        result = WalkForwardGovernanceService(policy, registry).evaluate(
            champion, challenger, "v1", "v2", {"threshold": 0.65}
        )
        assert result.valid and result.allowed
        assert result.recommendation == "PROMOTE_CHALLENGER"
        assert result.promotion_applied
        assert registry.active()["version"] == "v2"
        payload = walk_forward_governance_to_dict(result)
        json.dumps(payload)
        assert payload["challenger_version"] == "v2"

    weak = profile(60.0, 0.05, 0.50, -0.20, 0.15, 30.0, "SEVERE")
    rejected = WalkForwardGovernanceService().evaluate(champion, weak, "v1", "v3")
    assert rejected.valid and not rejected.allowed
    assert rejected.recommendation == "RETAIN_CHAMPION"
    assert rejected.rejection_reasons
    print("All walk-forward governance assertions passed.")


if __name__ == "__main__":
    main()
