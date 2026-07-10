import math
from collections import defaultdict

from trading_ai.strategy_engine.expected_move_engine import ExpectedMoveEngine
from trading_ai.strategy_engine.expiration_candidate import ExpirationCandidate
from trading_ai.strategy_engine.expiration_scoring import ExpirationScoring


class ExpirationOptimizer:
    def __init__(
        self,
        min_contracts_per_expiry: int = 4,
        min_avg_volume: float = 25.0,
        min_avg_open_interest: float = 100.0,
        max_avg_spread_pct: float = 0.35,
    ):
        self.min_contracts_per_expiry = int(min_contracts_per_expiry)
        self.min_avg_volume = float(min_avg_volume)
        self.min_avg_open_interest = float(min_avg_open_interest)
        self.max_avg_spread_pct = float(max_avg_spread_pct)

        self.scoring = ExpirationScoring()
        self.expected_move = ExpectedMoveEngine()

    def expected_move_profile_for_expiry(
        self,
        symbol: str,
        strategy: str,
        underlying_price: float,
        expiry: str,
        dte: int,
        option_chain,
        volatility_profile=None,
        atr: float = 0.0,
    ):
        historical_volatility = 0.0
        implied_volatility = 0.0

        if volatility_profile is not None:
            historical_volatility = float(
                getattr(
                    volatility_profile,
                    "hv30",
                    0.0,
                )
                or 0.0
            )

            implied_volatility = float(
                getattr(
                    volatility_profile,
                    "current_iv",
                    0.0,
                )
                or 0.0
            )

        return self.expected_move.analyze_from_option_chain(
            symbol=symbol,
            underlying_price=underlying_price,
            horizon_days=dte,
            option_chain=option_chain,
            implied_volatility=implied_volatility,
            historical_volatility=historical_volatility,
            atr=atr,
            target_expiry=expiry,
        )

    def optimize(
        self,
        symbol: str,
        strategy: str,
        underlying_price: float,
        option_chain,
        volatility_profile=None,
        top_n: int = 5,
    ) -> list[ExpirationCandidate]:
        rows = self._rows(option_chain)

        grouped = self._group_by_expiry(rows)

        candidates = []

        for expiry, expiry_rows in grouped.items():
            candidate = self._candidate_for_expiry(
                symbol=symbol,
                strategy=strategy,
                expiry=expiry,
                underlying_price=underlying_price,
                rows=expiry_rows,
                volatility_profile=volatility_profile,
            )

            if candidate:
                candidates.append(candidate)

        candidates.sort(key=lambda c: c.composite_score, reverse=True)
        return candidates[:top_n]

    def best(
        self,
        symbol: str,
        strategy: str,
        underlying_price: float,
        option_chain,
        volatility_profile=None,
    ) -> ExpirationCandidate | None:
        candidates = self.optimize(
            symbol=symbol,
            strategy=strategy,
            underlying_price=underlying_price,
            option_chain=option_chain,
            volatility_profile=volatility_profile,
            top_n=1,
        )

        return candidates[0] if candidates else None

    def _candidate_for_expiry(
        self,
        symbol: str,
        strategy: str,
        expiry: str,
        underlying_price: float,
        rows: list,
        volatility_profile=None,
    ) -> ExpirationCandidate | None:
        if not rows:
            return None

        dte = int(self._median([self._float(r, "dte") for r in rows]))

        contracts_available = len(rows)

        volumes = [self._float(r, "volume") for r in rows]
        open_interests = [self._float(r, "open_interest") for r in rows]
        spreads = [self._spread_pct(r) for r in rows]
        ivs = [self._float(r, "implied_volatility") for r in rows if self._float(r, "implied_volatility") > 0]
        deltas = [abs(self._float(r, "delta")) for r in rows]
        thetas = [abs(self._float(r, "theta")) for r in rows]
        vegas = [abs(self._float(r, "vega")) for r in rows]

        avg_volume = self._avg(volumes)
        avg_open_interest = self._avg(open_interests)
        avg_spread_pct = self._avg(spreads)
        avg_iv = self._avg(ivs)
        avg_abs_delta = self._avg(deltas)
        avg_abs_theta = self._avg(thetas)
        avg_vega = self._avg(vegas)

        volatility = avg_iv

        if volatility <= 0 and volatility_profile is not None:
            volatility = float(getattr(volatility_profile, "current_iv", 0.0) or 0.0)

        if volatility <= 0:
            volatility = 0.30

        expected_move = self.expected_move.calculate(
            underlying_price=underlying_price,
            volatility=volatility,
            dte=dte,
        )

        expected_move_pct = (
            expected_move / underlying_price
            if underlying_price > 0
            else 0.0
        )

        dte_score = self.scoring.dte_score(strategy, dte)

        liquidity_score = self.scoring.liquidity_score(
            avg_volume=avg_volume,
            avg_open_interest=avg_open_interest,
            avg_spread_pct=avg_spread_pct,
            contracts_available=contracts_available,
        )

        theta_score = self.scoring.theta_score(
            strategy=strategy,
            dte=dte,
            avg_abs_theta=avg_abs_theta,
        )

        volatility_score = self.scoring.volatility_score(
            strategy=strategy,
            avg_iv=avg_iv,
            volatility_profile=volatility_profile,
        )

        expected_move_score = self.scoring.expected_move_score(
            strategy=strategy,
            expected_move_pct=expected_move_pct,
        )

        composite = (
            dte_score * 0.25
            + liquidity_score * 0.25
            + theta_score * 0.20
            + volatility_score * 0.15
            + expected_move_score * 0.15
        )

        allowed = True
        warnings = []

        if contracts_available < self.min_contracts_per_expiry:
            warnings.append("Insufficient contracts for expiry")
            allowed = False

        if avg_volume < self.min_avg_volume:
            warnings.append("Low average volume")
            allowed = False

        if avg_open_interest < self.min_avg_open_interest:
            warnings.append("Low average open interest")
            allowed = False

        if avg_spread_pct > self.max_avg_spread_pct:
            warnings.append("Wide average spread")
            allowed = False

        if dte <= 0:
            warnings.append("Invalid DTE")
            allowed = False

        return ExpirationCandidate(
            symbol=symbol,
            strategy=strategy,
            expiry=str(expiry),
            dte=dte,
            underlying_price=float(underlying_price),
            contracts_available=contracts_available,
            avg_volume=round(avg_volume, 2),
            avg_open_interest=round(avg_open_interest, 2),
            avg_spread_pct=round(avg_spread_pct, 4),
            avg_iv=round(avg_iv, 4),
            avg_abs_delta=round(avg_abs_delta, 4),
            avg_abs_theta=round(avg_abs_theta, 4),
            avg_vega=round(avg_vega, 4),
            expected_move=round(expected_move, 2),
            expected_move_pct=round(expected_move_pct * 100.0, 2),
            dte_score=round(dte_score, 2),
            liquidity_score=round(liquidity_score, 2),
            theta_score=round(theta_score, 2),
            volatility_score=round(volatility_score, 2),
            expected_move_score=round(expected_move_score, 2),
            composite_score=round(composite, 2),
            reason=self._reason(strategy, dte, expected_move_pct),
            allowed=allowed,
            warnings=warnings,
        )

    def _reason(self, strategy: str, dte: int, expected_move_pct: float) -> str:
        return (
            f"{strategy} expiration with {dte} DTE and "
            f"{expected_move_pct * 100.0:.2f}% expected move."
        )

    def _group_by_expiry(self, rows):
        grouped = defaultdict(list)

        for row in rows:
            expiry = (
                self._get(row, "expiry")
                or self._get(row, "expiration")
                or self._get(row, "expiration_date")
                or "UNKNOWN"
            )

            grouped[str(expiry)].append(row)

        return grouped

    def _rows(self, option_chain):
        if option_chain is None:
            return []

        if hasattr(option_chain, "to_dict"):
            return option_chain.to_dict("records")

        return list(option_chain)

    def _get(self, row, key, default=None):
        if isinstance(row, dict):
            return row.get(key, default)

        return getattr(row, key, default)

    def _float(self, row, key, default=0.0):
        value = self._get(row, key, default)

        if value is None:
            return float(default)

        try:
            if isinstance(value, float) and math.isnan(value):
                return float(default)

            return float(value)

        except Exception:
            return float(default)

    def _spread_pct(self, row):
        spread_pct = self._float(row, "spread_pct")

        if spread_pct > 0:
            return spread_pct

        bid = self._float(row, "bid")
        ask = self._float(row, "ask")
        mid = self._mid(row)

        if mid <= 0:
            return 1.0

        return max(ask - bid, 0.0) / mid

    def _mid(self, row):
        mid = self._float(row, "mid")

        if mid > 0:
            return mid

        bid = self._float(row, "bid")
        ask = self._float(row, "ask")

        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0

        return self._float(row, "last")

    def _avg(self, values):
        values = [float(v) for v in values if v is not None]

        if not values:
            return 0.0

        return sum(values) / len(values)

    def _median(self, values):
        values = sorted(float(v) for v in values if v is not None)

        if not values:
            return 0.0

        mid = len(values) // 2

        if len(values) % 2:
            return values[mid]

        return (values[mid - 1] + values[mid]) / 2.0
