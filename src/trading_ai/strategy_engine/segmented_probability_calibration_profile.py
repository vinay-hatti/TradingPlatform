from dataclasses import dataclass, field

from trading_ai.strategy_engine.probability_calibration_profile import ProbabilityCalibrationProfile


@dataclass
class SegmentCalibrationResult:
    segment_key: str
    dimensions: dict[str, str]
    observation_count: int
    profile: ProbabilityCalibrationProfile
    priority: int


@dataclass
class SegmentedProbabilityCalibrationProfile:
    registry_id: str
    global_profile: ProbabilityCalibrationProfile | None
    segment_profiles: dict[str, SegmentCalibrationResult] = field(default_factory=dict)
    segment_count: int = 0
    valid_segment_count: int = 0
    observation_count: int = 0
    calibration_score: float = 0.0
    calibration_grade: str = "F"
    calibration_severity: str = "UNKNOWN"
    allowed: bool = False
    valid: bool = False
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
