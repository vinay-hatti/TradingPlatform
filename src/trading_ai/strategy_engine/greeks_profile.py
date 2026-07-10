from dataclasses import dataclass, field


@dataclass
class GreeksProfile:
    symbol: str
    strategy: str

    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    net_rho: float

    abs_delta: float
    abs_gamma: float
    abs_theta: float
    abs_vega: float

    delta_score: float
    gamma_score: float
    theta_score: float
    vega_score: float
    balance_score: float
    composite_score: float

    exposure_label: str
    reason: str

    allowed: bool = True
    warnings: list[str] = field(default_factory=list)
