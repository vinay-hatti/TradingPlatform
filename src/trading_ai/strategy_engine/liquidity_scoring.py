import math


class LiquidityScoring:
    def volume_score(self, volume: int) -> float:
        volume = max(int(volume or 0), 0)

        if volume >= 5000:
            return 100.0

        if volume >= 2000:
            return 92.0

        if volume >= 1000:
            return 84.0

        if volume >= 500:
            return 74.0

        if volume >= 250:
            return 64.0

        if volume >= 100:
            return 52.0

        if volume >= 50:
            return 40.0

        if volume > 0:
            return 20.0

        return 0.0

    def open_interest_score(self, open_interest: int) -> float:
        open_interest = max(int(open_interest or 0), 0)

        if open_interest >= 10000:
            return 100.0

        if open_interest >= 5000:
            return 94.0

        if open_interest >= 2500:
            return 86.0

        if open_interest >= 1000:
            return 75.0

        if open_interest >= 500:
            return 64.0

        if open_interest >= 250:
            return 52.0

        if open_interest >= 100:
            return 40.0

        if open_interest > 0:
            return 18.0

        return 0.0

    def spread_score(self, spread_pct: float) -> float:
        spread_pct = max(float(spread_pct or 0.0), 0.0)

        if spread_pct <= 0.02:
            return 100.0

        if spread_pct <= 0.05:
            return 94.0

        if spread_pct <= 0.08:
            return 86.0

        if spread_pct <= 0.10:
            return 78.0

        if spread_pct <= 0.15:
            return 66.0

        if spread_pct <= 0.20:
            return 54.0

        if spread_pct <= 0.30:
            return 38.0

        if spread_pct <= 0.50:
            return 18.0

        return 0.0

    def depth_score(
        self,
        bid_size: int,
        ask_size: int,
        requested_contracts: int,
    ) -> float:
        bid_size = max(int(bid_size or 0), 0)
        ask_size = max(int(ask_size or 0), 0)
        requested_contracts = max(int(requested_contracts or 1), 1)

        minimum_depth = min(bid_size, ask_size)

        if minimum_depth <= 0:
            return 10.0

        ratio = minimum_depth / requested_contracts

        if ratio >= 10:
            return 100.0

        if ratio >= 5:
            return 90.0

        if ratio >= 3:
            return 78.0

        if ratio >= 2:
            return 66.0

        if ratio >= 1:
            return 52.0

        if ratio >= 0.50:
            return 30.0

        return 12.0

    def capacity_score(
        self,
        requested_contracts: int,
        estimated_capacity: int,
    ) -> float:
        requested_contracts = max(int(requested_contracts or 1), 1)
        estimated_capacity = max(int(estimated_capacity or 0), 0)

        if estimated_capacity <= 0:
            return 0.0

        ratio = estimated_capacity / requested_contracts

        if ratio >= 10:
            return 100.0

        if ratio >= 5:
            return 90.0

        if ratio >= 3:
            return 78.0

        if ratio >= 2:
            return 64.0

        if ratio >= 1:
            return 50.0

        if ratio >= 0.50:
            return 25.0

        return 5.0

    def quote_quality_score(
        self,
        bid: float,
        ask: float,
        mid: float,
        last: float,
    ) -> float:
        bid = float(bid or 0.0)
        ask = float(ask or 0.0)
        mid = float(mid or 0.0)
        last = float(last or 0.0)

        if ask <= 0:
            return 0.0

        if bid < 0:
            return 0.0

        if ask < bid:
            return 0.0

        score = 45.0

        if bid > 0:
            score += 20.0

        if mid > 0:
            score += 20.0

        if last > 0:
            distance = abs(last - mid) / max(mid, 0.01)

            if distance <= 0.05:
                score += 15.0
            elif distance <= 0.15:
                score += 8.0

        return round(min(score, 100.0), 2)

    def composite_liquidity_score(
        self,
        volume_score: float,
        open_interest_score: float,
        spread_score: float,
        depth_score: float,
        capacity_score: float,
        quote_quality_score: float,
    ) -> float:
        score = (
            float(volume_score) * 0.20
            + float(open_interest_score) * 0.20
            + float(spread_score) * 0.25
            + float(depth_score) * 0.15
            + float(capacity_score) * 0.10
            + float(quote_quality_score) * 0.10
        )

        return round(max(0.0, min(100.0, score)), 2)

    def execution_score(
        self,
        liquidity_score: float,
        spread_pct: float,
        requested_contracts: int,
        estimated_capacity: int,
    ) -> float:
        liquidity_score = float(liquidity_score or 0.0)
        spread_pct = max(float(spread_pct or 0.0), 0.0)
        requested_contracts = max(int(requested_contracts or 1), 1)
        estimated_capacity = max(int(estimated_capacity or 0), 0)

        score = liquidity_score

        if spread_pct > 0.30:
            score -= 25.0
        elif spread_pct > 0.20:
            score -= 15.0
        elif spread_pct > 0.10:
            score -= 7.0

        if estimated_capacity < requested_contracts:
            score -= 25.0

        return round(max(0.0, min(100.0, score)), 2)

    def grade(self, score: float) -> str:
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

        if score >= 65:
            return "B-"

        if score >= 60:
            return "C+"

        if score >= 55:
            return "C"

        if score >= 45:
            return "D"

        return "F"

    def execution_quality(self, score: float) -> str:
        score = float(score or 0.0)

        if score >= 85:
            return "EXCELLENT"

        if score >= 70:
            return "GOOD"

        if score >= 55:
            return "ACCEPTABLE"

        if score >= 40:
            return "POOR"

        return "UNTRADEABLE"

    def safe_float(self, value, default=0.0) -> float:
        try:
            result = float(value)

            if math.isnan(result) or math.isinf(result):
                return float(default)

            return result

        except (TypeError, ValueError):
            return float(default)
