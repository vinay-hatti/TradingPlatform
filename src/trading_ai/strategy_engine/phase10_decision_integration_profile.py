from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Phase10DecisionIntegrationProfile:
    symbol: str
    valid: bool
    allowed: bool
    adaptive_available: bool
    learning_available: bool
    ensemble_available: bool
    online_adaptation_available: bool
    learning_state_registry_available: bool
    selected_strategy: str
    selected_direction: str
    adaptive_score: float
    adaptive_confidence_score: float
    ensemble_score: float
    meta_confidence_score: float
    consensus_ratio: float
    strategy_weight: float
    adaptation_score: float
    learning_state_version: str
    learning_state_champion_version: str
    learning_state_challenger_version: str
    grade: str
    severity: str
    recommendation: str
    adaptive_strategy_profile: Any = None
    strategy_learning_profile: Any = None
    dynamic_strategy_weighting_profile: Any = None
    ensemble_decision_profile: Any = None
    online_adaptation_profile: Any = None
    learning_state_registry_profile: Any = None
    learning_state_promotion_profile: Any = None
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
