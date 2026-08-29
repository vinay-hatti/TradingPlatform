from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SetupIntelligencePolicy:
    version: str = "M78-SETUP-POLICY-1.0"
    authority_effect: bool = False
    automatic_promotion: bool = False
    minimum_setup_quality: float = 55.0
    minimum_model_observations: int = 100
    minimum_positive_observations: int = 25
    minimum_negative_observations: int = 25
    minimum_distinct_dates: int = 20
    minimum_local_cell_observations: int = 30
    minimum_setup_prior_observations: int = 100
    shrinkage_strength: float = 100.0
    max_retest_distance_atr: float = 0.35
    min_breakout_hold_distance_atr: float = 0.10
    max_pullback_support_distance_atr: float = 0.75
    minimum_multi_timeframe_alignment: int = 2
    prospective_certification_required: bool = True
    minimum_prospective_observations: int = 30
    maximum_prospective_brier: float = 0.25


DEFAULT_POLICY = SetupIntelligencePolicy()
