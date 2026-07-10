from trading_ai.strategy_engine.greeks_profile import GreeksProfile
from trading_ai.strategy_engine.greeks_scoring import GreeksScoring


class GreeksOptimizer:
    def __init__(
        self,
        min_composite_score: float = 60.0,
        reject_extreme_gamma: bool = True,
    ):
        self.min_composite_score = float(min_composite_score)
        self.reject_extreme_gamma = bool(reject_extreme_gamma)
        self.scoring = GreeksScoring()

    def analyze_single_leg(
        self,
        symbol: str,
        strategy: str,
        delta: float,
        gamma: float,
        theta: float,
        vega: float,
        rho: float = 0.0,
    ) -> GreeksProfile:
        strategy = str(strategy or "").upper()
        target = self.scoring.target_for_strategy(strategy)

        net_delta = float(delta or 0.0)
        net_gamma = float(gamma or 0.0)
        net_theta = float(theta or 0.0)
        net_vega = float(vega or 0.0)
        net_rho = float(rho or 0.0)

        return self._profile(
            symbol=symbol,
            strategy=strategy,
            net_delta=net_delta,
            net_gamma=net_gamma,
            net_theta=net_theta,
            net_vega=net_vega,
            net_rho=net_rho,
            target=target,
        )

    def analyze_spread(
        self,
        symbol: str,
        strategy: str,
        short_leg,
        long_leg,
    ) -> GreeksProfile:
        strategy = str(strategy or "").upper()
        target = self.scoring.target_for_strategy(strategy)

        net_delta = self._float(short_leg, "delta") - self._float(long_leg, "delta")
        net_gamma = self._float(short_leg, "gamma") - self._float(long_leg, "gamma")
        net_theta = self._float(short_leg, "theta") - self._float(long_leg, "theta")
        net_vega = self._float(short_leg, "vega") - self._float(long_leg, "vega")
        net_rho = self._float(short_leg, "rho") - self._float(long_leg, "rho")

        return self._profile(
            symbol=symbol,
            strategy=strategy,
            net_delta=net_delta,
            net_gamma=net_gamma,
            net_theta=net_theta,
            net_vega=net_vega,
            net_rho=net_rho,
            target=target,
        )

    def analyze_multi_leg(
        self,
        symbol: str,
        strategy: str,
        legs: list[dict],
    ) -> GreeksProfile:
        strategy = str(strategy or "").upper()
        target = self.scoring.target_for_strategy(strategy)

        net_delta = 0.0
        net_gamma = 0.0
        net_theta = 0.0
        net_vega = 0.0
        net_rho = 0.0

        for leg in legs:
            action = str(leg.get("action", "LONG")).upper()
            qty = int(leg.get("quantity", 1) or 1)

            sign = 1.0 if action in {"LONG", "BUY"} else -1.0

            net_delta += sign * qty * float(leg.get("delta", 0.0) or 0.0)
            net_gamma += sign * qty * float(leg.get("gamma", 0.0) or 0.0)
            net_theta += sign * qty * float(leg.get("theta", 0.0) or 0.0)
            net_vega += sign * qty * float(leg.get("vega", 0.0) or 0.0)
            net_rho += sign * qty * float(leg.get("rho", 0.0) or 0.0)

        return self._profile(
            symbol=symbol,
            strategy=strategy,
            net_delta=net_delta,
            net_gamma=net_gamma,
            net_theta=net_theta,
            net_vega=net_vega,
            net_rho=net_rho,
            target=target,
        )

    def optimize_candidates(
        self,
        candidates: list,
        symbol: str | None = None,
    ) -> list:
        """
        Accepts StrikeCandidate or SpreadCandidate objects and attaches:
          - greeks_profile
          - greeks_composite_score
          - greeks_allowed
        """

        optimized = []

        for c in candidates:
            strategy = str(getattr(c, "strategy", "") or "").upper()
            candidate_symbol = symbol or getattr(c, "symbol", "")

            if hasattr(c, "delta"):
                profile = self.analyze_single_leg(
                    symbol=candidate_symbol,
                    strategy=strategy,
                    delta=getattr(c, "delta", 0.0),
                    gamma=getattr(c, "gamma", 0.0),
                    theta=getattr(c, "theta", 0.0),
                    vega=getattr(c, "vega", 0.0),
                    rho=getattr(c, "rho", 0.0),
                )
            elif hasattr(c, "net_delta"):
                profile = self._profile(
                    symbol=candidate_symbol,
                    strategy=strategy,
                    net_delta=getattr(c, "net_delta", 0.0),
                    net_gamma=0.0,
                    net_theta=getattr(c, "net_theta", 0.0),
                    net_vega=getattr(c, "net_vega", 0.0),
                    net_rho=0.0,
                    target=self.scoring.target_for_strategy(strategy),
                )
            else:
                continue

            setattr(c, "greeks_profile", profile)
            setattr(c, "greeks_composite_score", profile.composite_score)
            setattr(c, "greeks_allowed", profile.allowed)

            optimized.append(c)

        optimized.sort(
            key=lambda x: getattr(x, "greeks_composite_score", 0.0),
            reverse=True,
        )

        return optimized

    def _profile(
        self,
        symbol: str,
        strategy: str,
        net_delta: float,
        net_gamma: float,
        net_theta: float,
        net_vega: float,
        net_rho: float,
        target,
    ) -> GreeksProfile:
        delta_score = self.scoring.score_delta(net_delta, target)
        gamma_score = self.scoring.score_gamma(net_gamma, target)
        theta_score = self.scoring.score_theta(net_theta, target)
        vega_score = self.scoring.score_vega(net_vega, target)

        balance_score = self.scoring.balance_score(
            net_delta=net_delta,
            net_gamma=net_gamma,
            net_theta=net_theta,
            net_vega=net_vega,
            target=target,
        )

        composite = (
            delta_score * 0.30
            + gamma_score * 0.20
            + theta_score * 0.25
            + vega_score * 0.25
        )

        warnings = []
        allowed = True

        if composite < self.min_composite_score:
            warnings.append("Low Greeks composite score")
            allowed = False

        if self.reject_extreme_gamma and abs(net_gamma) > target.max_gamma * 2.0:
            warnings.append("Extreme gamma exposure")
            allowed = False

        if not (target.min_delta <= net_delta <= target.max_delta):
            warnings.append("Delta outside target range")

        if not (target.min_theta <= net_theta <= target.max_theta):
            warnings.append("Theta outside target range")

        if not (target.min_vega <= net_vega <= target.max_vega):
            warnings.append("Vega outside target range")

        exposure_label = self.scoring.exposure_label(
            net_delta=net_delta,
            net_theta=net_theta,
            net_vega=net_vega,
        )

        return GreeksProfile(
            symbol=symbol,
            strategy=strategy,
            net_delta=round(net_delta, 4),
            net_gamma=round(net_gamma, 5),
            net_theta=round(net_theta, 4),
            net_vega=round(net_vega, 4),
            net_rho=round(net_rho, 4),
            abs_delta=round(abs(net_delta), 4),
            abs_gamma=round(abs(net_gamma), 5),
            abs_theta=round(abs(net_theta), 4),
            abs_vega=round(abs(net_vega), 4),
            delta_score=round(delta_score, 2),
            gamma_score=round(gamma_score, 2),
            theta_score=round(theta_score, 2),
            vega_score=round(vega_score, 2),
            balance_score=round(balance_score, 2),
            composite_score=round(composite, 2),
            exposure_label=exposure_label,
            reason=self._reason(strategy, net_delta, net_theta, net_vega),
            allowed=allowed,
            warnings=warnings,
        )

    def _reason(self, strategy: str, net_delta: float, net_theta: float, net_vega: float) -> str:
        return (
            f"{strategy} Greeks exposure: "
            f"delta={net_delta:.2f}, theta={net_theta:.2f}, vega={net_vega:.2f}."
        )

    def _float(self, obj, key, default=0.0):
        if isinstance(obj, dict):
            value = obj.get(key, default)
        else:
            value = getattr(obj, key, default)

        try:
            return float(value or default)
        except Exception:
            return float(default)
