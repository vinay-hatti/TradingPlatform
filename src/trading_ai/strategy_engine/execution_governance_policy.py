from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecutionGovernancePolicy:
    """Policy thresholds for Phase 9 execution drift governance."""

    minimum_baseline_observations: int = 100
    minimum_current_observations: int = 50
    minimum_segment_observations: int = 20
    psi_bin_count: int = 10
    psi_epsilon: float = 1.0e-6

    moderate_psi_threshold: float = 0.10
    severe_psi_threshold: float = 0.25
    critical_psi_threshold: float = 0.50

    moderate_standardized_shift: float = 0.50
    severe_standardized_shift: float = 1.00
    critical_standardized_shift: float = 2.00

    maximum_shortfall_deterioration_bps: float = 15.0
    maximum_arrival_slippage_deterioration_bps: float = 12.0
    maximum_market_impact_deterioration_bps: float = 10.0
    maximum_effective_spread_deterioration_bps: float = 12.0
    maximum_latency_deterioration_seconds: float = 5.0
    maximum_fill_ratio_deterioration: float = 0.05
    maximum_execution_score_deterioration: float = 10.0

    minimum_governance_score: float = 60.0
    reject_severe_drift: bool = True
    reject_critical_drift: bool = True
    allow_insufficient_data: bool = True

    metric_weights: dict[str, float] = field(default_factory=lambda: {
        "implementation_shortfall_bps": 0.25,
        "arrival_slippage_bps": 0.15,
        "market_impact_bps": 0.15,
        "effective_spread_bps": 0.10,
        "fill_ratio": 0.15,
        "fill_delay_seconds": 0.10,
        "execution_score": 0.10,
    })
