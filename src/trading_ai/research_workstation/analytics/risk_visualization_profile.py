from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualizationSeriesProfile:
    name: str
    x_label: str
    y_label: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class RiskClassificationProfile:
    directional_exposure: str
    gamma_risk: str
    volatility_sensitivity: str
    time_decay_sensitivity: str
    assignment_risk: str
    capital_efficiency: str
    concentration_risk: str
