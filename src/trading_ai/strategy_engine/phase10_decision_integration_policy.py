from dataclasses import dataclass


@dataclass(frozen=True)
class Phase10DecisionIntegrationPolicy:
    """Governance controls for Phase 10 decision propagation."""

    require_ensemble_approval: bool = False
    reject_on_invalid_ensemble: bool = False
    prefer_ensemble_strategy: bool = True
    minimum_meta_confidence_score: float = 0.0
    minimum_ensemble_score: float = 0.0
    preserve_legacy_selection_on_unavailable: bool = True

    def validate(self) -> None:
        for name in ("minimum_meta_confidence_score", "minimum_ensemble_score"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100")
