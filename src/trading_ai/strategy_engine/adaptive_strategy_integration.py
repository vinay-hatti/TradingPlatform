from typing import Any

from trading_ai.strategy_engine.adaptive_strategy_serialization import adaptive_strategy_to_dict


def attach_adaptive_strategy_profile(target: Any, profile: Any) -> Any:
    """Attach Phase 10 results without requiring immediate Decision dataclass changes."""
    if target is None:
        return target
    if isinstance(target, dict):
        target["adaptive_strategy_profile"] = profile
        metadata = target.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata["adaptive_strategy_profile"] = adaptive_strategy_to_dict(profile)
        return target
    setattr(target, "adaptive_strategy_profile", profile)
    metadata = getattr(target, "metadata", None)
    if isinstance(metadata, dict):
        metadata["adaptive_strategy_profile"] = adaptive_strategy_to_dict(profile)
    return target
