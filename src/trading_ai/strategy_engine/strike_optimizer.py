import math

from trading_ai.strategy_engine.spread_candidate import SpreadCandidate
from trading_ai.strategy_engine.strike_candidate import StrikeCandidate
from trading_ai.strategy_engine.strike_scoring import StrikeScoring


class StrikeOptimizer:
    def __init__(
        self,
        min_volume: int = 50,
        min_open_interest: int = 100,
        max_spread_pct: float = 0.30,
    ):
        self.min_volume = int(min_volume)
        self.min_open_interest = int(min_open_interest)
        self.max_spread_pct = float(max_spread_pct)
        self.scoring = StrikeScoring()

    def optimize(
        self,
        symbol: str,
        strategy: str,
        underlying_price: float,
        option_chain,
        top_n: int = 5,
    ):
        strategy = str(strategy or "").upper()

        if strategy in {
            "LONG_CALL",
            "LONG_PUT",
            "SHORT_CALL",
            "SHORT_PUT",
        }:
            candidates = self.single_leg_candidates(
                symbol=symbol,
                strategy=strategy,
                underlying_price=underlying_price,
                option_chain=option_chain,
            )

        elif strategy in {
            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",
            "BULL_PUT_SPREAD",
            "BEAR_CALL_SPREAD",
        }:
            candidates = self.spread_candidates(
                symbol=symbol,
                strategy=strategy,
                underlying_price=underlying_price,
                option_chain=option_chain,
            )

        else:
            candidates = self.single_leg_candidates(
                symbol=symbol,
                strategy=strategy,
                underlying_price=underlying_price,
                option_chain=option_chain,
            )

        candidates.sort(key=lambda c: c.composite_score, reverse=True)
        return candidates[:top_n]

    def single_leg_candidates(
        self,
        symbol: str,
        strategy: str,
        underlying_price: float,
        option_chain,
    ) -> list[StrikeCandidate]:
        rows = self._rows(option_chain)

        option_type = self._option_type_for_strategy(strategy)
        candidates = []

        for row in rows:
            if self._row_option_type(row) != option_type:
                continue

            strike = self._float(row, "strike")
            bid = self._float(row, "bid")
            ask = self._float(row, "ask")
            mid = self._mid(row)
            last = self._float(row, "last")
            volume = int(self._float(row, "volume"))
            open_interest = int(self._float(row, "open_interest"))
            spread_pct = self._spread_pct(row)

            delta = self._float(row, "delta")
            gamma = self._float(row, "gamma")
            theta = self._float(row, "theta")
            vega = self._float(row, "vega")
            rho = self._float(row, "rho")
            iv = self._float(row, "implied_volatility")

            intrinsic = self._intrinsic(option_type, underlying_price, strike)
            extrinsic = max(mid - intrinsic, 0.0)

            liquidity_score = self.scoring.liquidity_score(
                volume=volume,
                open_interest=open_interest,
                spread_pct=spread_pct,
            )

            greek_score = self.scoring.single_leg_greek_score(
                strategy=strategy,
                option_type=option_type,
                delta=delta,
                gamma=gamma,
                theta=theta,
                vega=vega,
            )

            moneyness_score = self.scoring.moneyness_score(
                strategy=strategy,
                option_type=option_type,
                strike=strike,
                underlying_price=underlying_price,
            )

            value_score = self.scoring.value_score(
                mid=mid,
                intrinsic_value=intrinsic,
                extrinsic_value=extrinsic,
                implied_volatility=iv,
            )

            risk_score = self.scoring.risk_score(
                strategy=strategy,
                mid=mid,
                underlying_price=underlying_price,
                max_spread_pct=self.max_spread_pct,
                spread_pct=spread_pct,
            )

            composite = (
                liquidity_score * 0.30
                + greek_score * 0.30
                + moneyness_score * 0.20
                + value_score * 0.10
                + risk_score * 0.10
            )

            warnings = []
            allowed = True

            if volume < self.min_volume:
                warnings.append("Low volume")
                allowed = False

            if open_interest < self.min_open_interest:
                warnings.append("Low open interest")
                allowed = False

            if spread_pct > self.max_spread_pct:
                warnings.append("Wide bid/ask spread")
                allowed = False

            if mid <= 0:
                warnings.append("Invalid mid price")
                allowed = False

            candidate = StrikeCandidate(
                symbol=symbol,
                strategy=strategy,
                option_type=option_type,
                strike=strike,
                expiry=str(self._get(row, "expiry", "")),
                dte=int(self._float(row, "dte")),
                option_symbol=str(self._get(row, "option_symbol", "")),
                bid=bid,
                ask=ask,
                mid=mid,
                last=last,
                volume=volume,
                open_interest=open_interest,
                spread_pct=round(spread_pct, 4),
                delta=delta,
                gamma=gamma,
                theta=theta,
                vega=vega,
                rho=rho,
                implied_volatility=iv,
                underlying_price=float(underlying_price),
                moneyness_pct=round(
                    ((strike - underlying_price) / underlying_price) * 100.0,
                    2,
                ),
                intrinsic_value=round(intrinsic, 4),
                extrinsic_value=round(extrinsic, 4),
                liquidity_score=liquidity_score,
                greek_score=greek_score,
                moneyness_score=moneyness_score,
                value_score=value_score,
                risk_score=risk_score,
                composite_score=round(composite, 2),
                reason=self._reason(strategy, option_type, strike, underlying_price),
                allowed=allowed,
                warnings=warnings,
            )

            candidates.append(candidate)

        return candidates

    def spread_candidates(
        self,
        symbol: str,
        strategy: str,
        underlying_price: float,
        option_chain,
    ) -> list[SpreadCandidate]:
        rows = self._rows(option_chain)
        option_type = self._option_type_for_strategy(strategy)

        filtered = [
            r for r in rows
            if self._row_option_type(r) == option_type
        ]

        filtered.sort(key=lambda r: self._float(r, "strike"))

        candidates = []

        for i, short_leg in enumerate(filtered):
            for long_leg in filtered:
                short_strike = self._float(short_leg, "strike")
                long_strike = self._float(long_leg, "strike")

                if not self._valid_spread_structure(
                    strategy,
                    short_strike,
                    long_strike,
                    underlying_price,
                ):
                    continue

                short_mid = self._mid(short_leg)
                long_mid = self._mid(long_leg)
                width = abs(long_strike - short_strike)

                if width <= 0:
                    continue

                if strategy in {"BULL_PUT_SPREAD", "BEAR_CALL_SPREAD"}:
                    credit_or_debit = short_mid - long_mid
                    max_profit = credit_or_debit * 100.0
                    max_loss = (width - credit_or_debit) * 100.0
                else:
                    credit_or_debit = long_mid - short_mid
                    max_profit = max(width - credit_or_debit, 0.0) * 100.0
                    max_loss = credit_or_debit * 100.0

                if credit_or_debit <= 0 or max_loss <= 0:
                    continue

                short_liq = self.scoring.liquidity_score(
                    int(self._float(short_leg, "volume")),
                    int(self._float(short_leg, "open_interest")),
                    self._spread_pct(short_leg),
                )

                long_liq = self.scoring.liquidity_score(
                    int(self._float(long_leg, "volume")),
                    int(self._float(long_leg, "open_interest")),
                    self._spread_pct(long_leg),
                )

                liquidity_score = round((short_liq + long_liq) / 2.0, 2)

                short_delta = self._float(short_leg, "delta")
                long_delta = self._float(long_leg, "delta")
                net_delta = short_delta - long_delta

                net_theta = self._float(short_leg, "theta") - self._float(long_leg, "theta")
                net_vega = self._float(short_leg, "vega") - self._float(long_leg, "vega")

                greek_score = self._spread_greek_score(
                    strategy=strategy,
                    short_delta=short_delta,
                    long_delta=long_delta,
                    net_theta=net_theta,
                    net_vega=net_vega,
                )

                width_score = self._width_score(width, underlying_price)
                risk_reward_score = self._risk_reward_score(max_profit, max_loss)

                composite = (
                    liquidity_score * 0.35
                    + greek_score * 0.30
                    + width_score * 0.15
                    + risk_reward_score * 0.20
                )

                warnings = []
                allowed = True

                for leg_name, leg in [("short", short_leg), ("long", long_leg)]:
                    if int(self._float(leg, "volume")) < self.min_volume:
                        warnings.append(f"{leg_name} leg low volume")
                        allowed = False

                    if int(self._float(leg, "open_interest")) < self.min_open_interest:
                        warnings.append(f"{leg_name} leg low open interest")
                        allowed = False

                    if self._spread_pct(leg) > self.max_spread_pct:
                        warnings.append(f"{leg_name} leg wide spread")
                        allowed = False

                candidates.append(
                    SpreadCandidate(
                        symbol=symbol,
                        strategy=strategy,
                        option_type=option_type,
                        short_strike=short_strike,
                        long_strike=long_strike,
                        expiry=str(self._get(short_leg, "expiry", "")),
                        dte=int(self._float(short_leg, "dte")),
                        credit_or_debit=round(credit_or_debit, 4),
                        width=round(width, 4),
                        max_profit=round(max_profit, 2),
                        max_loss=round(max_loss, 2),
                        short_delta=short_delta,
                        long_delta=long_delta,
                        net_delta=round(net_delta, 4),
                        net_theta=round(net_theta, 4),
                        net_vega=round(net_vega, 4),
                        liquidity_score=liquidity_score,
                        greek_score=greek_score,
                        width_score=width_score,
                        risk_reward_score=risk_reward_score,
                        composite_score=round(composite, 2),
                        reason=self._spread_reason(strategy, short_strike, long_strike),
                        allowed=allowed,
                        warnings=warnings,
                    )
                )

        return candidates

    def _option_type_for_strategy(self, strategy: str) -> str:
        strategy = str(strategy or "").upper()

        if "PUT" in strategy:
            return "PUT"

        if "CALL" in strategy:
            return "CALL"

        return "CALL"

    def _valid_spread_structure(
        self,
        strategy: str,
        short_strike: float,
        long_strike: float,
        underlying_price: float,
    ) -> bool:
        strategy = str(strategy or "").upper()

        if strategy == "BULL_PUT_SPREAD":
            return long_strike < short_strike <= underlying_price

        if strategy == "BEAR_CALL_SPREAD":
            return long_strike > short_strike >= underlying_price

        if strategy == "BULL_CALL_SPREAD":
            return short_strike > long_strike >= underlying_price * 0.95

        if strategy == "BEAR_PUT_SPREAD":
            return short_strike < long_strike <= underlying_price * 1.05

        return False

    def _spread_greek_score(
        self,
        strategy: str,
        short_delta: float,
        long_delta: float,
        net_theta: float,
        net_vega: float,
    ) -> float:
        strategy = str(strategy or "").upper()

        net_delta = short_delta - long_delta
        score = 50.0

        if strategy in {"BULL_PUT_SPREAD", "BULL_CALL_SPREAD"}:
            if net_delta >= 0:
                score += 20.0

        if strategy in {"BEAR_CALL_SPREAD", "BEAR_PUT_SPREAD"}:
            if net_delta <= 0:
                score += 20.0

        if strategy in {"BULL_PUT_SPREAD", "BEAR_CALL_SPREAD"}:
            if net_theta >= 0:
                score += 15.0
            if net_vega <= 0:
                score += 15.0

        if strategy in {"BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"}:
            if abs(net_theta) <= 0.20:
                score += 15.0
            if abs(net_vega) <= 1.00:
                score += 15.0

        return round(min(score, 100.0), 2)

    def _width_score(self, width: float, underlying_price: float) -> float:
        width = float(width or 0.0)
        underlying_price = float(underlying_price or 0.0)

        if width <= 0 or underlying_price <= 0:
            return 0.0

        pct = width / underlying_price

        if 0.01 <= pct <= 0.05:
            return 100.0

        if 0.05 < pct <= 0.10:
            return 75.0

        return 45.0

    def _risk_reward_score(self, max_profit: float, max_loss: float) -> float:
        max_profit = float(max_profit or 0.0)
        max_loss = float(max_loss or 0.0)

        if max_profit <= 0 or max_loss <= 0:
            return 0.0

        ratio = max_profit / max_loss

        if ratio >= 0.50:
            return 100.0

        if ratio >= 0.33:
            return 80.0

        if ratio >= 0.20:
            return 60.0

        return 35.0

    def _reason(
        self,
        strategy: str,
        option_type: str,
        strike: float,
        underlying_price: float,
    ) -> str:
        distance = (
            abs(strike - underlying_price) / underlying_price * 100.0
            if underlying_price else 0.0
        )

        return (
            f"{strategy} {option_type} strike {strike:.2f} "
            f"is {distance:.2f}% from underlying."
        )

    def _spread_reason(self, strategy: str, short_strike: float, long_strike: float) -> str:
        return (
            f"{strategy} uses short strike {short_strike:.2f} "
            f"and long strike {long_strike:.2f}."
        )

    def _intrinsic(self, option_type: str, underlying_price: float, strike: float) -> float:
        option_type = str(option_type or "").upper()

        if option_type == "CALL":
            return max(float(underlying_price) - float(strike), 0.0)

        return max(float(strike) - float(underlying_price), 0.0)

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

    def _mid(self, row):
        mid = self._float(row, "mid")

        if mid > 0:
            return mid

        bid = self._float(row, "bid")
        ask = self._float(row, "ask")

        if bid > 0 and ask > 0:
            return (bid + ask) / 2.0

        return self._float(row, "last")

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

    def _row_option_type(self, row):
        value = (
            self._get(row, "option_type")
            or self._get(row, "type")
            or ""
        )

        return str(value).upper()
