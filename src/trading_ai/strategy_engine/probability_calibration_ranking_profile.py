from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProbabilityCalibrationRankingProfile:
    raw_ranking_score: float
    adjusted_ranking_score: float
    ranking_adjustment: float = 0.0
    raw_probability: float | None = None
    calibrated_probability: float | None = None
    probability_adjustment: float = 0.0
    calibration_weight: float = 0.0
    model_score: float = 0.0
    confidence_score: float = 0.0
    segment_key: str = "UNAVAILABLE"
    model_version: str = "UNAVAILABLE"
    method: str = "IDENTITY"
    grade: str = "N/A"
    severity: str = "UNKNOWN"
    allowed: bool = True
    valid: bool = False
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
