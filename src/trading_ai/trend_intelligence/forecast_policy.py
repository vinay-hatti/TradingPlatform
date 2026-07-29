from dataclasses import dataclass

@dataclass(frozen=True)
class TrendForecastPolicy:
    horizons: tuple[int, ...] = (5, 10, 20)
    minimum_history_rows: int = 126
    maximum_signal_adjustment: float = 1.5
    minimum_confidence_for_adjustment: float = 55.0
    annualization_days: int = 252

    def validate(self) -> None:
        if not self.horizons or any(h <= 0 for h in self.horizons):
            raise ValueError("forecast horizons must be positive")
        if self.minimum_history_rows < max(self.horizons) + 20:
            raise ValueError("minimum_history_rows is too small")
        if self.maximum_signal_adjustment < 0:
            raise ValueError("maximum_signal_adjustment must be non-negative")
