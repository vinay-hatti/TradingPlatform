class IVPercentile:
    def calculate(self, current_iv: float, iv_history: list[float]) -> float:
        current_iv = float(current_iv or 0.0)

        values = [
            float(v)
            for v in iv_history
            if v is not None and float(v) > 0
        ]

        if not values:
            return 0.0

        below = sum(1 for v in values if v <= current_iv)
        return round((below / len(values)) * 100.0, 2)
