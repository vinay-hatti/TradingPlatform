import math
import statistics


class ExpectedMoveScoring:
    def source_agreement_score(
        self,
        moves: list[float],
    ) -> float:
        values = [
            float(value)
            for value in moves
            if value is not None and float(value) > 0
        ]

        if len(values) < 2:
            return 40.0 if values else 0.0

        mean_value = statistics.mean(values)

        if mean_value <= 0:
            return 0.0

        if len(values) == 2:
            dispersion = abs(values[0] - values[1]) / mean_value
        else:
            dispersion = statistics.pstdev(values) / mean_value

        if dispersion <= 0.05:
            return 100.0

        if dispersion <= 0.10:
            return 92.0

        if dispersion <= 0.20:
            return 80.0

        if dispersion <= 0.30:
            return 65.0

        if dispersion <= 0.50:
            return 45.0

        return 20.0

    def confidence_score(
        self,
        source_count: int,
        agreement_score: float,
        iv_available: bool,
        straddle_available: bool,
        historical_available: bool,
        atr_available: bool,
    ) -> float:
        source_count = max(int(source_count or 0), 0)
        agreement_score = float(agreement_score or 0.0)

        availability_score = min(source_count / 4.0, 1.0) * 40.0

        source_quality = 0.0

        if straddle_available:
            source_quality += 25.0

        if iv_available:
            source_quality += 15.0

        if historical_available:
            source_quality += 10.0

        if atr_available:
            source_quality += 10.0

        score = (
            availability_score
            + source_quality
            + agreement_score * 0.40
        )

        return round(max(0.0, min(100.0, score)), 2)

    def confidence_grade(self, score: float) -> str:
        score = float(score or 0.0)

        if score >= 90:
            return "A+"

        if score >= 85:
            return "A"

        if score >= 80:
            return "A-"

        if score >= 75:
            return "B+"

        if score >= 70:
            return "B"

        if score >= 60:
            return "C"

        if score >= 45:
            return "D"

        return "F"

    def classify_move_regime(
        self,
        move_pct: float,
        horizon_days: int,
    ) -> str:
        move_pct = max(float(move_pct or 0.0), 0.0)
        horizon_days = max(int(horizon_days or 1), 1)

        normalized_daily_move = (
            move_pct / math.sqrt(horizon_days)
        )

        if normalized_daily_move >= 0.035:
            return "EXTREME_MOVE"

        if normalized_daily_move >= 0.022:
            return "HIGH_MOVE"

        if normalized_daily_move >= 0.012:
            return "NORMAL_MOVE"

        return "LOW_MOVE"

    def expansion_signal(
        self,
        implied_move: float,
        historical_move: float,
        straddle_move: float,
    ) -> str:
        implied_move = float(implied_move or 0.0)
        historical_move = float(historical_move or 0.0)
        straddle_move = float(straddle_move or 0.0)

        reference_moves = [
            value
            for value in [
                historical_move,
                straddle_move,
            ]
            if value > 0
        ]

        if implied_move <= 0 or not reference_moves:
            return "INSUFFICIENT_DATA"

        reference = sum(reference_moves) / len(reference_moves)

        ratio = implied_move / reference if reference > 0 else 0.0

        if ratio >= 1.30:
            return "IMPLIED_MOVE_OVERPRICED"

        if ratio <= 0.75:
            return "IMPLIED_MOVE_UNDERPRICED"

        return "IMPLIED_MOVE_FAIR"
