from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchCasePolicy:
    minimum_base_case_probability: float = 0.20
    maximum_base_case_probability: float = 0.80
    minimum_total_scenario_probability: float = 0.999
    maximum_total_scenario_probability: float = 1.001
    minimum_evidence_items: int = 1
    minimum_assumptions: int = 1
    minimum_scenarios: int = 3
    maximum_scenarios: int = 12
    minimum_case_confidence: float = 0.50
    require_base_case: bool = True
    require_bull_case: bool = True
    require_bear_case: bool = True
    require_invalidation_condition: bool = True
    require_time_horizon: bool = True
    require_primary_thesis: bool = True

    def validate(self) -> None:
        probability_fields = (
            "minimum_base_case_probability",
            "maximum_base_case_probability",
            "minimum_total_scenario_probability",
            "maximum_total_scenario_probability",
            "minimum_case_confidence",
        )
        for name in probability_fields:
            value = float(getattr(self, name))
            if value < 0.0:
                raise ValueError(f"{name} cannot be negative.")

        if self.minimum_base_case_probability > 1.0:
            raise ValueError(
                "minimum_base_case_probability cannot exceed 1."
            )
        if self.maximum_base_case_probability > 1.0:
            raise ValueError(
                "maximum_base_case_probability cannot exceed 1."
            )
        if (
            self.minimum_base_case_probability
            > self.maximum_base_case_probability
        ):
            raise ValueError(
                "Minimum base-case probability cannot exceed maximum."
            )
        if self.minimum_scenarios <= 0:
            raise ValueError("minimum_scenarios must be positive.")
        if self.maximum_scenarios < self.minimum_scenarios:
            raise ValueError(
                "maximum_scenarios cannot be below minimum_scenarios."
            )
        if self.minimum_evidence_items < 0:
            raise ValueError(
                "minimum_evidence_items cannot be negative."
            )
        if self.minimum_assumptions < 0:
            raise ValueError(
                "minimum_assumptions cannot be negative."
            )
