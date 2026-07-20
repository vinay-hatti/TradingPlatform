from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GreeksLegProfile:
    symbol: str
    option_type: str
    side: str
    quantity: int
    multiplier: int
    strike: float
    expiration: str
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    delta_exposure: float
    gamma_exposure: float
    theta_exposure: float
    vega_exposure: float
    rho_exposure: float


@dataclass(frozen=True)
class GreeksExposureProfile:
    total_delta: float
    total_gamma: float
    total_theta: float
    total_vega: float
    total_rho: float
    delta_classification: str
    gamma_risk: str
    volatility_sensitivity: str
    time_decay_sensitivity: str
    leg_count: int
    legs: tuple[GreeksLegProfile, ...]
