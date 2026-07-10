from dataclasses import dataclass


@dataclass
class GreeksTarget:
    strategy: str

    min_delta: float
    max_delta: float

    max_gamma: float

    min_theta: float
    max_theta: float

    min_vega: float
    max_vega: float

    preferred_theta_sign: str
    preferred_vega_sign: str
    preferred_delta_sign: str
