class IVRank:
    def calculate(self, current_iv: float, iv_low: float, iv_high: float) -> float:
        current_iv = float(current_iv or 0.0)
        iv_low = float(iv_low or 0.0)
        iv_high = float(iv_high or 0.0)

        if iv_high <= iv_low:
            return 0.0

        rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100.0
        return max(0.0, min(100.0, rank))

