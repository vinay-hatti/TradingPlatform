from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProbabilityCalibrationRuntimeProfile:
    raw_probability: float | None
    calibrated_probability: float | None
    adjustment: float = 0.0
    adjustment_pct: float = 0.0
    segment_key: str = "UNAVAILABLE"
    model_version: str = "UNAVAILABLE"
    model_method: str = "IDENTITY"
    model_score: float = 0.0
    model_grade: str = "N/A"
    model_severity: str = "UNKNOWN"
    confidence_score: float = 0.0
    allowed: bool = True
    valid: bool = False
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
