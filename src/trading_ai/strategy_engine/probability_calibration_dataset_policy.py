from dataclasses import dataclass


@dataclass(frozen=True)
class ProbabilityCalibrationDatasetPolicy:
    probability_fields: tuple[str, ...] = (
        "raw_probability", "probability_of_profit", "predicted_probability", "pop"
    )
    outcome_fields: tuple[str, ...] = (
        "outcome", "won", "is_win", "profitable", "realized_success"
    )
    pnl_fields: tuple[str, ...] = ("net_pnl", "pnl", "realized_pnl")
    timestamp_fields: tuple[str, ...] = ("exit_date", "entry_date", "timestamp", "date")
    symbol_fields: tuple[str, ...] = ("symbol", "underlying_symbol")
    strategy_fields: tuple[str, ...] = ("strategy", "strategy_name")
    direction_fields: tuple[str, ...] = ("direction", "signal", "option_type")
    regime_fields: tuple[str, ...] = ("market_regime", "regime", "volatility_regime")
    weight_fields: tuple[str, ...] = ("sample_weight", "weight")
    infer_outcome_from_pnl: bool = True
    winning_pnl_threshold: float = 0.0
    discard_missing_probability: bool = True
    discard_missing_outcome: bool = True
    clamp_probabilities: bool = True
    probability_floor: float = 1e-6
    probability_ceiling: float = 1.0 - 1e-6

    def validate(self) -> None:
        if not self.probability_fields:
            raise ValueError("probability_fields cannot be empty")
        if not self.outcome_fields and not self.infer_outcome_from_pnl:
            raise ValueError("an outcome source is required")
        if not 0.0 < self.probability_floor < self.probability_ceiling < 1.0:
            raise ValueError("probability bounds are invalid")
