from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioOptimizationFrontierPolicy:
    """Configuration for deterministic portfolio-optimization sensitivity sweeps."""

    exposure_levels: tuple[float, ...] = (0.20, 0.30, 0.40, 0.50)
    risk_levels: tuple[float, ...] = (0.08, 0.12, 0.16, 0.20)
    concentration_levels: tuple[float, ...] = (0.20, 0.25, 0.30)
    include_concentration_sweep: bool = True
    minimum_valid_points: int = 3
    stability_weight_tolerance_pct: float = 0.02
    maximum_points: int = 48

    def validate(self) -> None:
        for field_name, values in {
            "exposure_levels": self.exposure_levels,
            "risk_levels": self.risk_levels,
            "concentration_levels": self.concentration_levels,
        }.items():
            if not values:
                raise ValueError(f"{field_name} cannot be empty")
            for value in values:
                if value <= 0.0 or value > 1.0:
                    raise ValueError(f"{field_name} values must be in (0, 1]")
        if self.minimum_valid_points <= 0:
            raise ValueError("minimum_valid_points must be positive")
        if self.stability_weight_tolerance_pct < 0.0 or self.stability_weight_tolerance_pct > 1.0:
            raise ValueError("stability_weight_tolerance_pct must be between 0 and 1")
        if self.maximum_points <= 0:
            raise ValueError("maximum_points must be positive")
