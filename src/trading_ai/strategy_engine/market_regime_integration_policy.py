from dataclasses import dataclass

@dataclass(frozen=True)
class MarketRegimeIntegrationPolicy:
    enabled: bool = True
    require_valid_regime: bool = False
    reject_critical_regime: bool = False
    minimum_regime_score: float = 40.0
    minimum_forecast_score: float = 35.0
    minimum_breadth_score: float = 35.0
    strategy_adaptation_enabled: bool = True
    maximum_strategy_score_adjustment: float = 10.0
    maximum_ranking_score_adjustment: float = 7.5
    stress_penalty: float = 10.0
    aligned_strategy_bonus: float = 7.5
    transition_penalty: float = 4.0

    def validate(self):
        for name in ("minimum_regime_score", "minimum_forecast_score", "minimum_breadth_score"):
            value=float(getattr(self,name))
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100")
        if self.maximum_strategy_score_adjustment < 0 or self.maximum_ranking_score_adjustment < 0:
            raise ValueError("adjustment limits must be non-negative")
