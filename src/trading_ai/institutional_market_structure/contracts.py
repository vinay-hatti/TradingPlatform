from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass(frozen=True)
class DealerPositioningPolicy:
    contract_multiplier: int = 100
    risk_free_rate: float = 0.04
    dealer_sign_convention: str = "street_proxy"
    minimum_open_interest: int = 1
    minimum_volume: int = 0
    minimum_dte: int = 1
    maximum_dte: int = 365
    maximum_snapshot_age_days: int = 3
    target_dte: int = 30
    expected_move_minimum_dte: int = 7
    expected_move_maximum_dte: int = 45
    gamma_grid_min_factor: float = 0.70
    gamma_grid_max_factor: float = 1.30
    gamma_grid_steps: int = 121
    minimum_midpoint: float = 0.01
    maximum_trade_spread_pct: float = 0.35
    confidence_minimum_rows: int = 50
    confidence_minimum_oi: int = 10_000

@dataclass(frozen=True)
class MetricProvenance:
    metric_name: str
    metric_class: str
    source: str
    estimator: str | None = None
    confidence: float = 1.0

@dataclass(frozen=True)
class StrikeExposure:
    expiry: str
    dte: int
    strike: float
    call_open_interest: float = 0.0
    put_open_interest: float = 0.0
    call_volume: float = 0.0
    put_volume: float = 0.0
    call_gamma_exposure: float = 0.0
    put_gamma_exposure: float = 0.0
    net_gamma_exposure: float = 0.0
    call_delta_exposure: float = 0.0
    put_delta_exposure: float = 0.0
    net_delta_exposure: float = 0.0
    vanna_exposure: float = 0.0
    charm_exposure: float = 0.0
    call_spread_pct: float | None = None
    put_spread_pct: float | None = None
    liquidity_score: float = 0.0
    dealer_pressure_score: float = 0.0
    pin_score: float = 0.0
    market_structure_eligible: bool = True
    trade_eligible: bool = False

@dataclass(frozen=True)
class ExpirationExposure:
    expiry: str
    dte: int
    call_open_interest: float
    put_open_interest: float
    net_gamma_exposure: float
    net_delta_exposure: float
    net_vanna_exposure: float
    net_charm_exposure: float
    atm_implied_volatility: float | None
    expected_move: float | None
    liquidity_score: float

@dataclass(frozen=True)
class IVSurfacePoint:
    expiry: str
    dte: int
    strike: float
    option_type: str
    moneyness: float
    delta: float | None
    implied_volatility: float
    bid: float
    ask: float
    mid: float
    spread_pct: float | None

@dataclass(frozen=True)
class HistoricalComparison:
    previous_snapshot_date: str | None = None
    open_interest_change: float | None = None
    gamma_exposure_change: float | None = None
    delta_exposure_change: float | None = None
    call_wall_migration: float | None = None
    put_wall_migration: float | None = None
    gamma_flip_migration: float | None = None
    iv_term_slope_change: float | None = None
    put_skew_change: float | None = None

@dataclass(frozen=True)
class InstitutionalMarketStructureSnapshot:
    symbol: str
    as_of_date: str
    option_snapshot_date: str
    spot: float
    source_table: str
    source_contract_count: int
    executable_contract_count: int
    quote_coverage_pct: float
    dealer_sign_convention: str
    estimator_name: str
    estimator_version: str
    unsigned_gamma_exposure: float
    unsigned_delta_exposure: float
    net_gamma_exposure: float
    net_delta_exposure: float
    net_vanna_exposure: float
    net_charm_exposure: float
    gamma_regime: str
    gamma_flip: float | None
    gamma_flip_distance_pct: float | None
    gamma_flip_lower_bound: float | None
    gamma_flip_upper_bound: float | None
    gamma_flip_confidence: float
    primary_call_wall: float | None
    secondary_call_wall: float | None
    primary_put_wall: float | None
    secondary_put_wall: float | None
    magnet_strike: float | None
    dealer_support: float | None
    dealer_resistance: float | None
    expected_move: float | None
    expected_move_pct: float | None
    expected_move_upper: float | None
    expected_move_lower: float | None
    atm_iv: float | None
    iv_term_slope: float | None
    put_skew: float | None
    call_skew: float | None
    volatility_risk_premium: float | None
    snapshot_activity_call_premium: float
    snapshot_activity_put_premium: float
    dealer_hedging_pressure: float
    institutional_positioning_score: float
    positioning_label: str
    bull_probability: float
    bear_probability: float
    range_probability: float
    breakout_probability: float
    breakdown_probability: float
    volatility_expansion_probability: float
    volatility_compression_probability: float
    pin_risk: float
    confidence: str
    confidence_score: float
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    provenance: tuple[MetricProvenance, ...] = field(default_factory=tuple)
    historical_comparison: HistoricalComparison = field(default_factory=HistoricalComparison)
    strike_exposures: tuple[StrikeExposure, ...] = field(default_factory=tuple)
    expiration_exposures: tuple[ExpirationExposure, ...] = field(default_factory=tuple)
    iv_surface: tuple[IVSurfacePoint, ...] = field(default_factory=tuple)

    @property
    def call_wall(self) -> float | None:
        return self.primary_call_wall

    @property
    def put_wall(self) -> float | None:
        return self.primary_put_wall

    @property
    def zero_gamma(self) -> float | None:
        return self.gamma_flip

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
