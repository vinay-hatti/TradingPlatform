from typing import Any

from trading_ai.strategy_engine.ensemble_decision_serialization import ensemble_to_dict


def attach_ensemble_decision(target: Any, profile: Any) -> Any:
    payload = ensemble_to_dict(profile)
    if isinstance(target, dict):
        target["ensemble_decision_profile"] = profile
        target["ensemble_score"] = payload.get("ensemble_score", 0.0)
        target["ensemble_allowed"] = payload.get("allowed", False)
        target["ensemble_selected_strategy"] = payload.get("selected_strategy")
        target.setdefault("metadata", {})["ensemble_decision_profile"] = profile
        return target
    metadata = getattr(target, "metadata", None)
    if isinstance(metadata, dict):
        metadata["ensemble_decision_profile"] = profile
    for name, value in (
        ("ensemble_decision_profile", profile),
        ("ensemble_score", payload.get("ensemble_score", 0.0)),
        ("ensemble_allowed", payload.get("allowed", False)),
        ("ensemble_selected_strategy", payload.get("selected_strategy")),
    ):
        try:
            setattr(target, name, value)
        except Exception:
            pass
    return target
