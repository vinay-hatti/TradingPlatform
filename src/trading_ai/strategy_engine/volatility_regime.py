class VolatilityRegimeClassifier:
    def classify(
        self,
        iv_rank: float,
        iv_percentile: float,
        iv_hv_ratio: float,
    ) -> str:
        iv_rank = float(iv_rank or 0.0)
        iv_percentile = float(iv_percentile or 0.0)
        iv_hv_ratio = float(iv_hv_ratio or 0.0)

        if iv_rank >= 80 or iv_percentile >= 85 or iv_hv_ratio >= 1.75:
            return "EXTREME_HIGH_VOL"

        if iv_rank >= 60 or iv_percentile >= 70 or iv_hv_ratio >= 1.35:
            return "HIGH_VOL"

        if iv_rank <= 20 and iv_percentile <= 30 and iv_hv_ratio <= 0.85:
            return "LOW_VOL"

        return "NORMAL_VOL"

    def signal(self, regime: str) -> str:
        if regime in {"EXTREME_HIGH_VOL", "HIGH_VOL"}:
            return "VOL_COMPRESSION_CANDIDATE"

        if regime == "LOW_VOL":
            return "VOL_EXPANSION_CANDIDATE"

        return "NEUTRAL_VOL"
