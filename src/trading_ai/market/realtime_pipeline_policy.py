from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RealTimePipelinePolicy:
    maximum_queue_size: int = 10000
    reject_when_queue_full: bool = True
    stop_on_dispatch_error: bool = False
    retain_rejected_events: bool = True
    maximum_rejected_events: int = 1000
    require_monotonic_sequence: bool = True
    maximum_sequence_gap: int = 1000
    fail_closed: bool = True
    minimum_pipeline_score: float = 85.0

    def validate(self) -> None:
        if self.maximum_queue_size <= 0:
            raise ValueError("maximum_queue_size must be positive")
        if self.maximum_rejected_events < 0:
            raise ValueError("maximum_rejected_events cannot be negative")
        if self.maximum_sequence_gap < 0:
            raise ValueError("maximum_sequence_gap cannot be negative")
        if not 0.0 <= self.minimum_pipeline_score <= 100.0:
            raise ValueError("minimum_pipeline_score must be between 0 and 100")
