from dataclasses import dataclass

from trading_ai.options.quality import OptionQualityScorer


@dataclass
class RankedOption:
    option: object
    rank: int
    total_score: float
    option_score: float
    probability_of_profit: float
    liquidity_score: float
    delta_score: float
    iv_score: float
    dte_score: float
    spread_score: float
    spread_pct: float
    atm_score: float
    option_score_contribution: float
    atm_score_contribution: float
    dte_score_contribution: float
    liquidity_contribution: float
    spread_contribution: float
    option_weight: float
    atm_weight: float
    dte_weight: float
    liquidity_weight: float
    spread_weight: float


class OptionRanker:

    def __init__(self):
        self.quality = OptionQualityScorer()

    def _days_to_expiry(self, option):
        from datetime import datetime

        dte = getattr(option, "days_to_expiry", None)

        if dte is not None:
            return int(dte)

        expiry = getattr(option, "expiry", None)

        if expiry is None:
            return 30

        try:
            expiry_dt = datetime.strptime(str(expiry), "%Y-%m-%d")
            today = datetime.now()
            return max((expiry_dt - today).days, 0)
        except Exception:
            return 30

    def _dte_score(self, option):
        dte = self._days_to_expiry(option)

        if 45 <= dte <= 120:
            return 100.0

        if 121 <= dte <= 180:
            return 90.0

        if 181 <= dte <= 270:
            return 80.0

        if 271 <= dte <= 365:
            return 65.0

        if 30 <= dte <= 44:
            return 50.0

        if dte < 30:
            return 20.0

        return 40.0

    def _spread_metrics(self, option):
        bid = float(getattr(option, "bid", 0.0) or 0.0)
        ask = float(getattr(option, "ask", 0.0) or 0.0)

        if bid <= 0 or ask <= 0 or ask < bid:
            return None, 35.0

        mid = (bid + ask) / 2.0

        if mid <= 0:
            return None, 35.0

        spread_pct = (ask - bid) / mid

        if spread_pct <= 0.01:
            spread_score = 100.0
        elif spread_pct <= 0.03:
            spread_score = 90.0
        elif spread_pct <= 0.05:
            spread_score = 75.0
        elif spread_pct <= 0.10:
            spread_score = 50.0
        elif spread_pct <= 0.20:
            spread_score = 25.0
        else:
            spread_score = 5.0

        return spread_pct, spread_score

    def _atm_score(self, option, spot):
        if spot is None or spot <= 0:
            return 50.0

        strike = float(getattr(option, "strike", 0.0) or 0.0)

        if strike <= 0:
            return 50.0

        distance = abs(strike - spot) / spot

        if distance <= 0.02:
            return 100.0

        if distance <= 0.05:
            return 90.0

        if distance <= 0.10:
            return 75.0

        if distance <= 0.15:
            return 55.0

        if distance <= 0.20:
            return 35.0

        return 15.0

    def rank(self, options, signal, limit=None, spot=None):
        ranked = []

        option_weight = 0.40
        atm_weight = 0.20
        dte_weight = 0.15
        liquidity_weight = 0.15
        spread_weight = 0.10

        for option in options:
            quality = self.quality.score(
                option,
                signal,
                spot=spot,
            )

            dte_score = self._dte_score(option)
            spread_pct, spread_score = self._spread_metrics(option)
            atm_score = self._atm_score(option, spot)

            option_score_contribution = (
                quality["option_score"] * option_weight
            )
            atm_score_contribution = atm_score * atm_weight
            dte_score_contribution = dte_score * dte_weight
            liquidity_contribution = (
                quality["liquidity_score"] * liquidity_weight
            )
            spread_contribution = spread_score * spread_weight

            total_score = (
                option_score_contribution
                + atm_score_contribution
                + dte_score_contribution
                + liquidity_contribution
                + spread_contribution
            )

            ranked.append(
                RankedOption(
                    option=option,
                    rank=0,
                    total_score=total_score,
                    option_score=quality["option_score"],
                    probability_of_profit=quality["probability_of_profit"],
                    liquidity_score=quality["liquidity_score"],
                    delta_score=quality["delta_score"],
                    iv_score=quality["iv_score"],
                    dte_score=dte_score,
                    spread_score=spread_score,
                    spread_pct=spread_pct if spread_pct is not None else -1.0,
                    atm_score=atm_score,
                    option_score_contribution=option_score_contribution,
                    atm_score_contribution=atm_score_contribution,
                    dte_score_contribution=dte_score_contribution,
                    liquidity_contribution=liquidity_contribution,
                    spread_contribution=spread_contribution,
                    option_weight=option_weight,
                    atm_weight=atm_weight,
                    dte_weight=dte_weight,
                    liquidity_weight=liquidity_weight,
                    spread_weight=spread_weight,
                )
            )

        ranked = sorted(
            ranked,
            key=lambda r: r.total_score,
            reverse=True,
        )

        for idx, ranked_option in enumerate(ranked, start=1):
            ranked_option.rank = idx

        if limit is not None:
            return ranked[:limit]

        return ranked
