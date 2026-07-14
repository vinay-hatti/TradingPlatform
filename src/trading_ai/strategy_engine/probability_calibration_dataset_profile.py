from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProbabilityCalibrationObservation:
    probability: float
    outcome: int
    timestamp: Any = None
    symbol: str = "UNKNOWN"
    strategy: str = "UNKNOWN"
    direction: str = "UNKNOWN"
    market_regime: str = "UNKNOWN"
    sample_weight: float = 1.0
    source_index: int = -1
    metadata: dict = field(default_factory=dict)


@dataclass
class ProbabilityCalibrationDataset:
    observations: list[ProbabilityCalibrationObservation] = field(default_factory=list)
    input_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    rejection_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def probabilities(self) -> list[float]:
        return [item.probability for item in self.observations]

    @property
    def outcomes(self) -> list[int]:
        return [item.outcome for item in self.observations]

    @property
    def timestamps(self) -> list:
        return [item.timestamp for item in self.observations]

    @property
    def sample_weights(self) -> list[float]:
        return [item.sample_weight for item in self.observations]

    @property
    def valid(self) -> bool:
        return self.accepted_count > 0
