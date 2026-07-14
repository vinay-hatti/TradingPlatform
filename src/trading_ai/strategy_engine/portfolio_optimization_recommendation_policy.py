from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioOptimizationRecommendationPolicy:
    minimum_frontier_score: float = 60.0
    minimum_stability_score: float = 55.0
    maximum_constraint_sensitivity_score: float = 70.0
    reject_critical_frontier: bool = True
    prefer_pareto_points: bool = True

    def validate(self) -> None:
        for name, value in {
            "minimum_frontier_score": self.minimum_frontier_score,
            "minimum_stability_score": self.minimum_stability_score,
            "maximum_constraint_sensitivity_score": self.maximum_constraint_sensitivity_score,
        }.items():
            if value < 0.0 or value > 100.0:
                raise ValueError(f"{name} must be between 0 and 100")
