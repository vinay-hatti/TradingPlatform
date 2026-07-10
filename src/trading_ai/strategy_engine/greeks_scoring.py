from trading_ai.strategy_engine.greeks_target import GreeksTarget


class GreeksScoring:
    def target_for_strategy(self, strategy: str) -> GreeksTarget:
        strategy = str(strategy or "").upper()

        if strategy == "LONG_CALL":
            return GreeksTarget(
                strategy=strategy,
                min_delta=0.40,
                max_delta=0.70,
                max_gamma=0.15,
                min_theta=-0.20,
                max_theta=0.00,
                min_vega=0.05,
                max_vega=1.50,
                preferred_theta_sign="NEGATIVE",
                preferred_vega_sign="POSITIVE",
                preferred_delta_sign="POSITIVE",
            )

        if strategy == "LONG_PUT":
            return GreeksTarget(
                strategy=strategy,
                min_delta=-0.70,
                max_delta=-0.40,
                max_gamma=0.15,
                min_theta=-0.20,
                max_theta=0.00,
                min_vega=0.05,
                max_vega=1.50,
                preferred_theta_sign="NEGATIVE",
                preferred_vega_sign="POSITIVE",
                preferred_delta_sign="NEGATIVE",
            )

        if strategy in {"BULL_CALL_SPREAD", "BULL_PUT_SPREAD"}:
            return GreeksTarget(
                strategy=strategy,
                min_delta=0.10,
                max_delta=0.45,
                max_gamma=0.12,
                min_theta=-0.15,
                max_theta=0.15,
                min_vega=-0.80,
                max_vega=0.80,
                preferred_theta_sign="ANY",
                preferred_vega_sign="ANY",
                preferred_delta_sign="POSITIVE",
            )

        if strategy in {"BEAR_PUT_SPREAD", "BEAR_CALL_SPREAD"}:
            return GreeksTarget(
                strategy=strategy,
                min_delta=-0.45,
                max_delta=-0.10,
                max_gamma=0.12,
                min_theta=-0.15,
                max_theta=0.15,
                min_vega=-0.80,
                max_vega=0.80,
                preferred_theta_sign="ANY",
                preferred_vega_sign="ANY",
                preferred_delta_sign="NEGATIVE",
            )

        if strategy in {"IRON_CONDOR", "IRON_BUTTERFLY"}:
            return GreeksTarget(
                strategy=strategy,
                min_delta=-0.10,
                max_delta=0.10,
                max_gamma=0.08,
                min_theta=0.00,
                max_theta=0.25,
                min_vega=-1.50,
                max_vega=0.00,
                preferred_theta_sign="POSITIVE",
                preferred_vega_sign="NEGATIVE",
                preferred_delta_sign="NEUTRAL",
            )

        if strategy in {"LONG_STRADDLE", "LONG_STRANGLE"}:
            return GreeksTarget(
                strategy=strategy,
                min_delta=-0.15,
                max_delta=0.15,
                max_gamma=0.20,
                min_theta=-0.35,
                max_theta=0.00,
                min_vega=0.10,
                max_vega=2.50,
                preferred_theta_sign="NEGATIVE",
                preferred_vega_sign="POSITIVE",
                preferred_delta_sign="NEUTRAL",
            )

        return GreeksTarget(
            strategy=strategy,
            min_delta=-0.50,
            max_delta=0.50,
            max_gamma=0.20,
            min_theta=-0.25,
            max_theta=0.25,
            min_vega=-1.50,
            max_vega=1.50,
            preferred_theta_sign="ANY",
            preferred_vega_sign="ANY",
            preferred_delta_sign="ANY",
        )

    def score_delta(self, net_delta: float, target: GreeksTarget) -> float:
        net_delta = float(net_delta or 0.0)

        if target.min_delta <= net_delta <= target.max_delta:
            return 100.0

        distance = min(
            abs(net_delta - target.min_delta),
            abs(net_delta - target.max_delta),
        )

        return round(max(0.0, 100.0 - distance * 200.0), 2)

    def score_gamma(self, net_gamma: float, target: GreeksTarget) -> float:
        net_gamma = abs(float(net_gamma or 0.0))

        if net_gamma <= target.max_gamma:
            return 100.0

        excess = net_gamma - target.max_gamma
        return round(max(0.0, 100.0 - excess * 500.0), 2)

    def score_theta(self, net_theta: float, target: GreeksTarget) -> float:
        net_theta = float(net_theta or 0.0)

        in_range = target.min_theta <= net_theta <= target.max_theta

        score = 100.0 if in_range else 60.0

        if target.preferred_theta_sign == "POSITIVE" and net_theta < 0:
            score -= 35.0

        if target.preferred_theta_sign == "NEGATIVE" and net_theta > 0:
            score -= 25.0

        if abs(net_theta) > max(abs(target.min_theta), abs(target.max_theta), 0.01):
            score -= 20.0

        return round(max(0.0, min(100.0, score)), 2)

    def score_vega(self, net_vega: float, target: GreeksTarget) -> float:
        net_vega = float(net_vega or 0.0)

        in_range = target.min_vega <= net_vega <= target.max_vega

        score = 100.0 if in_range else 60.0

        if target.preferred_vega_sign == "POSITIVE" and net_vega < 0:
            score -= 35.0

        if target.preferred_vega_sign == "NEGATIVE" and net_vega > 0:
            score -= 35.0

        return round(max(0.0, min(100.0, score)), 2)

    def balance_score(
        self,
        net_delta: float,
        net_gamma: float,
        net_theta: float,
        net_vega: float,
        target: GreeksTarget,
    ) -> float:
        delta_score = self.score_delta(net_delta, target)
        gamma_score = self.score_gamma(net_gamma, target)
        theta_score = self.score_theta(net_theta, target)
        vega_score = self.score_vega(net_vega, target)

        balance = (
            delta_score * 0.35
            + gamma_score * 0.20
            + theta_score * 0.25
            + vega_score * 0.20
        )

        return round(balance, 2)

    def exposure_label(
        self,
        net_delta: float,
        net_theta: float,
        net_vega: float,
    ) -> str:
        parts = []

        if net_delta > 0.10:
            parts.append("LONG_DELTA")
        elif net_delta < -0.10:
            parts.append("SHORT_DELTA")
        else:
            parts.append("DELTA_NEUTRAL")

        if net_theta > 0.01:
            parts.append("POSITIVE_THETA")
        elif net_theta < -0.01:
            parts.append("NEGATIVE_THETA")
        else:
            parts.append("THETA_NEUTRAL")

        if net_vega > 0.05:
            parts.append("LONG_VEGA")
        elif net_vega < -0.05:
            parts.append("SHORT_VEGA")
        else:
            parts.append("VEGA_NEUTRAL")

        return "_".join(parts)
