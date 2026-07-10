import math

from trading_ai.strategy_engine.execution_estimator import ExecutionEstimator
from trading_ai.strategy_engine.liquidity_profile import LiquidityProfile
from trading_ai.strategy_engine.liquidity_scoring import LiquidityScoring
from trading_ai.strategy_engine.liquidity_thresholds import LiquidityThresholds
from trading_ai.strategy_engine.multi_leg_liquidity_profile import (
    MultiLegLiquidityProfile,
)


class LiquidityEngine:
    def __init__(
        self,
        thresholds: LiquidityThresholds | None = None,
    ):
        self.thresholds = thresholds or LiquidityThresholds()
        self.scoring = LiquidityScoring()
        self.execution = ExecutionEstimator()

    def analyze_contract(
        self,
        symbol: str,
        contract,
        requested_contracts: int = 1,
    ) -> LiquidityProfile:
        requested_contracts = max(int(requested_contracts or 1), 1)

        option_symbol = str(
            self._get(contract, "option_symbol", "")
            or self._get(contract, "symbol", "")
            or ""
        )

        bid = self._float(contract, "bid")
        ask = self._float(contract, "ask")
        last = self._float(contract, "last")

        mid = self._float(contract, "mid")

        if mid <= 0 and bid >= 0 and ask > 0:
            mid = (bid + ask) / 2.0

        volume = int(self._float(contract, "volume"))
        open_interest = int(self._float(contract, "open_interest"))

        bid_size = int(
            self._float(
                contract,
                "bid_size",
                self._float(contract, "bidSize", 0),
            )
        )

        ask_size = int(
            self._float(
                contract,
                "ask_size",
                self._float(contract, "askSize", 0),
            )
        )

        absolute_spread = max(ask - bid, 0.0)

        spread_pct = self._float(contract, "spread_pct")

        if spread_pct <= 0:
            spread_pct = (
                absolute_spread / mid
                if mid > 0
                else 1.0
            )

        quoted_depth = min(bid_size, ask_size)

        estimated_capacity = self.execution.estimate_capacity(
            volume=volume,
            open_interest=open_interest,
            bid_size=bid_size,
            ask_size=ask_size,
            max_volume_ratio=self.thresholds.max_contracts_to_volume_ratio,
            max_open_interest_ratio=(
                self.thresholds.max_contracts_to_open_interest_ratio
            ),
        )

        volume_score = self.scoring.volume_score(volume)
        open_interest_score = self.scoring.open_interest_score(open_interest)
        spread_score = self.scoring.spread_score(spread_pct)

        depth_score = self.scoring.depth_score(
            bid_size=bid_size,
            ask_size=ask_size,
            requested_contracts=requested_contracts,
        )

        capacity_score = self.scoring.capacity_score(
            requested_contracts=requested_contracts,
            estimated_capacity=estimated_capacity,
        )

        quote_quality_score = self.scoring.quote_quality_score(
            bid=bid,
            ask=ask,
            mid=mid,
            last=last,
        )

        liquidity_score = self.scoring.composite_liquidity_score(
            volume_score=volume_score,
            open_interest_score=open_interest_score,
            spread_score=spread_score,
            depth_score=depth_score,
            capacity_score=capacity_score,
            quote_quality_score=quote_quality_score,
        )

        execution_score = self.scoring.execution_score(
            liquidity_score=liquidity_score,
            spread_pct=spread_pct,
            requested_contracts=requested_contracts,
            estimated_capacity=estimated_capacity,
        )

        estimated_buy_price = self.execution.estimate_buy_price(
            bid=bid,
            ask=ask,
            requested_contracts=requested_contracts,
            estimated_capacity=estimated_capacity,
            spread_pct=spread_pct,
        )

        estimated_sell_price = self.execution.estimate_sell_price(
            bid=bid,
            ask=ask,
            requested_contracts=requested_contracts,
            estimated_capacity=estimated_capacity,
            spread_pct=spread_pct,
        )

        round_trip_slippage, round_trip_slippage_pct = (
            self.execution.round_trip_slippage(
                mid=mid,
                estimated_buy_price=estimated_buy_price,
                estimated_sell_price=estimated_sell_price,
                contracts=requested_contracts,
            )
        )

        warnings = self._contract_warnings(
            bid=bid,
            ask=ask,
            mid=mid,
            volume=volume,
            open_interest=open_interest,
            spread_pct=spread_pct,
            quoted_depth=quoted_depth,
            requested_contracts=requested_contracts,
            estimated_capacity=estimated_capacity,
            liquidity_score=liquidity_score,
            execution_score=execution_score,
        )

        allowed = not any(
            warning.startswith("REJECT:")
            for warning in warnings
        )

        warnings = [
            warning.replace("REJECT: ", "")
            for warning in warnings
        ]

        grade = self.scoring.grade(liquidity_score)
        execution_quality = self.scoring.execution_quality(execution_score)

        return LiquidityProfile(
            symbol=symbol,
            option_symbol=option_symbol,
            bid=round(bid, 4),
            ask=round(ask, 4),
            mid=round(mid, 4),
            last=round(last, 4),
            volume=volume,
            open_interest=open_interest,
            absolute_spread=round(absolute_spread, 4),
            spread_pct=round(spread_pct, 4),
            bid_size=bid_size,
            ask_size=ask_size,
            quoted_depth=quoted_depth,
            requested_contracts=requested_contracts,
            estimated_capacity=estimated_capacity,
            volume_score=round(volume_score, 2),
            open_interest_score=round(open_interest_score, 2),
            spread_score=round(spread_score, 2),
            depth_score=round(depth_score, 2),
            capacity_score=round(capacity_score, 2),
            quote_quality_score=round(quote_quality_score, 2),
            liquidity_score=round(liquidity_score, 2),
            execution_score=round(execution_score, 2),
            estimated_buy_price=estimated_buy_price,
            estimated_sell_price=estimated_sell_price,
            estimated_round_trip_slippage=round_trip_slippage,
            estimated_round_trip_slippage_pct=round(
                round_trip_slippage_pct * 100.0,
                2,
            ),
            liquidity_grade=grade,
            execution_quality=execution_quality,
            allowed=allowed,
            reason=self._contract_reason(
                option_symbol=option_symbol,
                score=liquidity_score,
                execution_score=execution_score,
                spread_pct=spread_pct,
            ),
            warnings=warnings,
        )

    def analyze_multi_leg(
        self,
        symbol: str,
        strategy: str,
        legs: list,
        requested_contracts: int = 1,
    ) -> MultiLegLiquidityProfile:
        requested_contracts = max(int(requested_contracts or 1), 1)

        leg_profiles = []

        package_mid = 0.0
        estimated_package_price = 0.0
        total_absolute_spread = 0.0

        for leg in legs:
            contract = leg.get("contract", leg)
            action = str(leg.get("action", "BUY")).upper()
            quantity = max(int(leg.get("quantity", 1) or 1), 1)

            leg_requested_contracts = requested_contracts * quantity

            profile = self.analyze_contract(
                symbol=symbol,
                contract=contract,
                requested_contracts=leg_requested_contracts,
            )

            leg_profiles.append(profile)

            sign = 1.0 if action in {"BUY", "LONG"} else -1.0

            package_mid += sign * quantity * profile.mid

            if sign > 0:
                estimated_package_price += (
                    quantity * profile.estimated_buy_price
                )
            else:
                estimated_package_price -= (
                    quantity * profile.estimated_sell_price
                )

            total_absolute_spread += (
                quantity * profile.absolute_spread
            )

        if not leg_profiles:
            return MultiLegLiquidityProfile(
                symbol=symbol,
                strategy=strategy,
                legs=[],
                leg_count=0,
                requested_contracts=requested_contracts,
                package_mid=0.0,
                estimated_package_price=0.0,
                total_absolute_spread=0.0,
                package_spread_pct=0.0,
                minimum_leg_liquidity_score=0.0,
                average_leg_liquidity_score=0.0,
                package_liquidity_score=0.0,
                execution_score=0.0,
                estimated_round_trip_slippage=0.0,
                estimated_round_trip_slippage_pct=0.0,
                weakest_leg="",
                liquidity_grade="F",
                execution_quality="UNTRADEABLE",
                allowed=False,
                reason="No strategy legs supplied.",
                warnings=["No legs supplied"],
            )

        minimum_leg_score = min(
            p.liquidity_score
            for p in leg_profiles
        )

        average_leg_score = sum(
            p.liquidity_score
            for p in leg_profiles
        ) / len(leg_profiles)

        average_execution_score = sum(
            p.execution_score
            for p in leg_profiles
        ) / len(leg_profiles)

        package_spread_pct = (
            total_absolute_spread / abs(package_mid)
            if abs(package_mid) > 0.01
            else 1.0
        )

        spread_score = self.scoring.spread_score(package_spread_pct)

        package_liquidity_score = (
            minimum_leg_score * 0.40
            + average_leg_score * 0.35
            + spread_score * 0.25
        )

        execution_score = (
            average_execution_score * 0.65
            + minimum_leg_score * 0.20
            + spread_score * 0.15
        )

        weakest_profile = min(
            leg_profiles,
            key=lambda p: p.liquidity_score,
        )

        total_slippage = sum(
            profile.estimated_round_trip_slippage
            for profile in leg_profiles
        )

        total_slippage_pct = (
            total_slippage
            / max(abs(package_mid) * requested_contracts * 100.0, 0.01)
        )

        warnings = []

        for profile in leg_profiles:
            if not profile.allowed:
                warnings.append(
                    f"Leg {profile.option_symbol or 'UNKNOWN'} is not tradeable"
                )

        if package_spread_pct > self.thresholds.max_spread_pct:
            warnings.append("Package spread exceeds maximum")

        if minimum_leg_score < self.thresholds.minimum_liquidity_score:
            warnings.append("Weakest leg liquidity is below minimum")

        if execution_score < self.thresholds.minimum_execution_score:
            warnings.append("Package execution score is below minimum")

        allowed = (
            all(profile.allowed for profile in leg_profiles)
            and package_spread_pct <= self.thresholds.max_spread_pct
            and minimum_leg_score >= self.thresholds.minimum_liquidity_score
            and execution_score >= self.thresholds.minimum_execution_score
        )

        grade = self.scoring.grade(package_liquidity_score)
        execution_quality = self.scoring.execution_quality(execution_score)

        return MultiLegLiquidityProfile(
            symbol=symbol,
            strategy=strategy,
            legs=leg_profiles,
            leg_count=len(leg_profiles),
            requested_contracts=requested_contracts,
            package_mid=round(package_mid, 4),
            estimated_package_price=round(estimated_package_price, 4),
            total_absolute_spread=round(total_absolute_spread, 4),
            package_spread_pct=round(package_spread_pct, 4),
            minimum_leg_liquidity_score=round(minimum_leg_score, 2),
            average_leg_liquidity_score=round(average_leg_score, 2),
            package_liquidity_score=round(package_liquidity_score, 2),
            execution_score=round(execution_score, 2),
            estimated_round_trip_slippage=round(total_slippage, 2),
            estimated_round_trip_slippage_pct=round(
                total_slippage_pct * 100.0,
                2,
            ),
            weakest_leg=weakest_profile.option_symbol,
            liquidity_grade=grade,
            execution_quality=execution_quality,
            allowed=allowed,
            reason=(
                f"{strategy} package liquidity score "
                f"{package_liquidity_score:.2f}; "
                f"weakest leg {weakest_profile.option_symbol or 'UNKNOWN'}."
            ),
            warnings=warnings,
        )

    def rank_contracts(
        self,
        symbol: str,
        option_chain,
        requested_contracts: int = 1,
        allowed_only: bool = False,
    ) -> list[LiquidityProfile]:
        rows = self._rows(option_chain)

        profiles = [
            self.analyze_contract(
                symbol=symbol,
                contract=row,
                requested_contracts=requested_contracts,
            )
            for row in rows
        ]

        if allowed_only:
            profiles = [
                profile
                for profile in profiles
                if profile.allowed
            ]

        profiles.sort(
            key=lambda p: (
                p.allowed,
                p.liquidity_score,
                p.execution_score,
            ),
            reverse=True,
        )

        return profiles

    def attach_to_candidates(
        self,
        candidates: list,
        requested_contracts: int = 1,
    ) -> list:
        updated = []

        for candidate in candidates:
            if not hasattr(candidate, "bid"):
                updated.append(candidate)
                continue

            profile = self.analyze_contract(
                symbol=getattr(candidate, "symbol", ""),
                contract=candidate,
                requested_contracts=requested_contracts,
            )

            setattr(candidate, "liquidity_profile", profile)
            setattr(
                candidate,
                "institutional_liquidity_score",
                profile.liquidity_score,
            )
            setattr(
                candidate,
                "institutional_execution_score",
                profile.execution_score,
            )
            setattr(
                candidate,
                "institutional_liquidity_allowed",
                profile.allowed,
            )

            existing_score = float(
                getattr(candidate, "composite_score", 0.0) or 0.0
            )

            adjusted_score = (
                existing_score * 0.65
                + profile.liquidity_score * 0.20
                + profile.execution_score * 0.15
            )

            setattr(
                candidate,
                "institutional_composite_score",
                round(adjusted_score, 2),
            )

            updated.append(candidate)

        updated.sort(
            key=lambda c: getattr(
                c,
                "institutional_composite_score",
                getattr(c, "composite_score", 0.0),
            ),
            reverse=True,
        )

        return updated

    def _contract_warnings(
        self,
        bid: float,
        ask: float,
        mid: float,
        volume: int,
        open_interest: int,
        spread_pct: float,
        quoted_depth: int,
        requested_contracts: int,
        estimated_capacity: int,
        liquidity_score: float,
        execution_score: float,
    ) -> list[str]:
        warnings = []

        if self.thresholds.reject_zero_bid and bid <= 0:
            warnings.append("REJECT: Zero bid")

        if self.thresholds.reject_crossed_market and ask < bid:
            warnings.append("REJECT: Crossed market")

        if (
            self.thresholds.reject_locked_market
            and ask == bid
            and ask > 0
        ):
            warnings.append("REJECT: Locked market")

        if ask <= 0:
            warnings.append("REJECT: Invalid ask")

        if mid < self.thresholds.min_mid:
            warnings.append("REJECT: Mid price below minimum")

        if volume < self.thresholds.min_volume:
            warnings.append("REJECT: Volume below minimum")

        if open_interest < self.thresholds.min_open_interest:
            warnings.append("REJECT: Open interest below minimum")

        if spread_pct > self.thresholds.max_spread_pct:
            warnings.append("REJECT: Spread exceeds maximum")

        if quoted_depth < self.thresholds.min_quoted_depth:
            warnings.append("Limited quoted depth")

        if estimated_capacity < requested_contracts:
            warnings.append(
                "REJECT: Requested contracts exceed estimated capacity"
            )

        if liquidity_score < self.thresholds.minimum_liquidity_score:
            warnings.append("REJECT: Liquidity score below minimum")

        if execution_score < self.thresholds.minimum_execution_score:
            warnings.append("REJECT: Execution score below minimum")

        return warnings

    def _contract_reason(
        self,
        option_symbol: str,
        score: float,
        execution_score: float,
        spread_pct: float,
    ) -> str:
        return (
            f"{option_symbol or 'Option contract'} liquidity={score:.2f}, "
            f"execution={execution_score:.2f}, "
            f"spread={spread_pct:.2%}."
        )

    def _rows(self, option_chain):
        if option_chain is None:
            return []

        if hasattr(option_chain, "to_dict"):
            return option_chain.to_dict("records")

        return list(option_chain)

    def _get(self, obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    def _float(self, obj, key, default=0.0):
        value = self._get(obj, key, default)

        try:
            result = float(value)

            if math.isnan(result) or math.isinf(result):
                return float(default)

            return result

        except (TypeError, ValueError):
            return float(default)
