from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniversePipelinePolicy:
    minimum_symbol_count: int = 6000
    maximum_source_age_hours: int = 72
    strict_providers: bool = False
    require_nonempty_eligible_universe: bool = True
    require_checksum_validation: bool = True
    continue_on_degraded_metrics: bool = True

    def validate(self) -> None:
        if self.minimum_symbol_count < 1:
            raise ValueError("minimum_symbol_count must be positive")
        if self.maximum_source_age_hours < 1:
            raise ValueError("maximum_source_age_hours must be positive")
