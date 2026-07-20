from __future__ import annotations

import math
from datetime import date
from typing import Iterable, Mapping, Any

from .trade_construction_policy import TradeConstructionPolicy
from .trade_construction_profile import (
    CapitalRequirementProfile,
    StrategyBlueprintProfile,
    TradeConstructionProfile,
    TradeLegBlueprintProfile,
    TradeTicketProfile,
    TradeValidationCheckProfile,
)


class TradeConstructionEngine:
    def __init__(
        self,
        policy: TradeConstructionPolicy | None = None,
    ) -> None:
        self.policy = policy or TradeConstructionPolicy()
        self.policy.validate()

    @staticmethod
    def _get(source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    @staticmethod
    def _severity(rejections: int, warnings: int) -> str:
        if rejections >= 2:
            return "CRITICAL"
        if rejections == 1:
            return "HIGH"
        if warnings >= 2:
            return "MODERATE"
        if warnings == 1:
            return "LOW"
        return "NONE"

    def _leg(
        self,
        source: Any,
        *,
        symbol: str,
        quantity_ratio: int,
    ) -> TradeLegBlueprintProfile:
        bid = float(self._get(source, "bid", 0.0) or 0.0)
        ask = float(self._get(source, "ask", 0.0) or 0.0)
        mark = float(
            self._get(source, "mark", (bid + ask) / 2.0) or 0.0
        )
        side = str(self._get(source, "side", "LONG")).upper()
        buffer = self.policy.limit_price_buffer_pct
        limit_price = (
            min(ask, mark * (1.0 + buffer))
            if side == "LONG"
            else max(bid, mark * (1.0 - buffer))
        )
        spread_pct = (
            (ask - bid) / mark
            if mark > 0
            else 1.0
        )
        expiration = self._get(source, "expiration")
        if not isinstance(expiration, date):
            raise ValueError("Every leg requires a date expiration.")

        return TradeLegBlueprintProfile(
            symbol=symbol,
            expiration=expiration,
            option_type=str(
                self._get(source, "option_type", "")
            ).upper(),
            side=side,
            strike=float(self._get(source, "strike", 0.0)),
            quantity_ratio=int(quantity_ratio),
            bid=round(bid, 6),
            ask=round(ask, 6),
            mark=round(mark, 6),
            limit_price=round(limit_price, 6),
            spread_pct=round(spread_pct, 6),
            open_interest=int(
                self._get(source, "open_interest", 0) or 0
            ),
            volume=int(self._get(source, "volume", 0) or 0),
            delta=self._get(source, "delta"),
            gamma=self._get(source, "gamma"),
            theta=self._get(source, "theta"),
            vega=self._get(source, "vega"),
        )

    def _blueprint(
        self,
        *,
        symbol: str,
        strategy_name: str,
        direction: str,
        leg_sources: Iterable[Any],
        quantity_ratios: Iterable[int] | None,
        maximum_profit_per_contract: float | None,
        maximum_loss_per_contract: float | None,
        probability_of_profit: float,
        breakeven_points: Iterable[float],
    ) -> StrategyBlueprintProfile:
        sources = tuple(leg_sources)
        ratios = tuple(quantity_ratios or (1 for _ in sources))
        if not sources:
            raise ValueError("At least one option leg is required.")
        if len(sources) != len(ratios):
            raise ValueError(
                "Quantity ratios must match the number of legs."
            )
        if any(int(ratio) <= 0 for ratio in ratios):
            raise ValueError("Quantity ratios must be positive.")

        legs = tuple(
            self._leg(
                source,
                symbol=symbol,
                quantity_ratio=int(ratio),
            )
            for source, ratio in zip(sources, ratios)
        )
        expirations = {leg.expiration for leg in legs}
        if len(expirations) != 1:
            raise ValueError(
                "Step 1 trade tickets require a common expiration."
            )

        signed = sum(
            (
                leg.limit_price
                if leg.side == "SHORT"
                else -leg.limit_price
            )
            * leg.quantity_ratio
            for leg in legs
        )
        net_credit_debit = signed * self.policy.contract_multiplier
        defined_risk = (
            maximum_loss_per_contract is not None
            and maximum_loss_per_contract >= 0
        )
        reward_risk_ratio = (
            float(maximum_profit_per_contract)
            / float(maximum_loss_per_contract)
            if maximum_profit_per_contract is not None
            and maximum_loss_per_contract not in {None, 0}
            else 0.0
        )

        return StrategyBlueprintProfile(
            symbol=symbol,
            strategy_name=strategy_name,
            direction=direction.upper(),
            order_side=(
                "CREDIT" if net_credit_debit >= 0 else "DEBIT"
            ),
            order_type="LIMIT",
            time_in_force="DAY",
            legs=legs,
            net_limit_price=round(abs(signed), 6),
            net_credit_debit=round(net_credit_debit, 6),
            defined_risk=defined_risk,
            maximum_profit_per_contract=maximum_profit_per_contract,
            maximum_loss_per_contract=maximum_loss_per_contract,
            reward_risk_ratio=round(reward_risk_ratio, 6),
            probability_of_profit=float(probability_of_profit),
            breakeven_points=tuple(
                round(float(point), 6)
                for point in breakeven_points
            ),
        )

    def _capital(
        self,
        *,
        blueprint: StrategyBlueprintProfile,
        account_equity: float,
        requested_contracts: int | None,
    ) -> CapitalRequirementProfile:
        if account_equity <= 0:
            raise ValueError("Account equity must be positive.")

        risk_budget = (
            account_equity * self.policy.maximum_position_risk_pct
        )
        buying_power_budget = (
            account_equity * self.policy.maximum_buying_power_pct
        )
        risk_per_contract = float(
            blueprint.maximum_loss_per_contract
            if blueprint.maximum_loss_per_contract is not None
            else account_equity
        )
        buying_power_per_contract = max(
            risk_per_contract,
            abs(blueprint.net_credit_debit),
        )

        risk_limited = (
            math.floor(risk_budget / risk_per_contract)
            if risk_per_contract > 0
            else self.policy.maximum_contracts
        )
        bp_limited = (
            math.floor(
                buying_power_budget / buying_power_per_contract
            )
            if buying_power_per_contract > 0
            else self.policy.maximum_contracts
        )
        requested = (
            int(requested_contracts)
            if requested_contracts is not None
            else self.policy.maximum_contracts
        )
        policy_limited = min(
            requested,
            self.policy.maximum_contracts,
        )
        recommended = max(
            0,
            min(risk_limited, bp_limited, policy_limited),
        )
        if recommended < self.policy.minimum_contracts:
            recommended = 0

        total_risk = risk_per_contract * recommended
        total_bp = buying_power_per_contract * recommended

        return CapitalRequirementProfile(
            account_equity=round(account_equity, 6),
            requested_risk_budget=round(risk_budget, 6),
            requested_buying_power_budget=round(
                buying_power_budget, 6
            ),
            risk_per_contract=round(risk_per_contract, 6),
            buying_power_per_contract=round(
                buying_power_per_contract, 6
            ),
            risk_limited_contracts=max(0, risk_limited),
            buying_power_limited_contracts=max(0, bp_limited),
            policy_limited_contracts=max(0, policy_limited),
            recommended_contracts=recommended,
            total_maximum_risk=round(total_risk, 6),
            estimated_buying_power=round(total_bp, 6),
            position_risk_pct=round(
                total_risk / account_equity, 6
            ),
            buying_power_pct=round(total_bp / account_equity, 6),
        )

    def _checks(
        self,
        blueprint: StrategyBlueprintProfile,
        capital: CapitalRequirementProfile,
    ) -> tuple[TradeValidationCheckProfile, ...]:
        legs = blueprint.legs
        worst_spread = max(leg.spread_pct for leg in legs)
        minimum_oi = min(leg.open_interest for leg in legs)
        minimum_volume = min(leg.volume for leg in legs)

        return (
            TradeValidationCheckProfile(
                name="DEFINED_RISK",
                passed=(
                    blueprint.defined_risk
                    or not self.policy.require_defined_risk_for_approval
                ),
                severity="ERROR",
                actual=str(blueprint.defined_risk),
                limit=str(
                    self.policy.require_defined_risk_for_approval
                ),
                message="Strategy risk must be explicitly bounded.",
            ),
            TradeValidationCheckProfile(
                name="POSITION_RISK",
                passed=(
                    capital.position_risk_pct
                    <= self.policy.maximum_position_risk_pct
                    and capital.recommended_contracts > 0
                ),
                severity="ERROR",
                actual=f"{capital.position_risk_pct:.4f}",
                limit=f"{self.policy.maximum_position_risk_pct:.4f}",
                message="Position maximum risk must fit policy.",
            ),
            TradeValidationCheckProfile(
                name="BUYING_POWER",
                passed=(
                    capital.buying_power_pct
                    <= self.policy.maximum_buying_power_pct
                    and capital.recommended_contracts > 0
                ),
                severity="ERROR",
                actual=f"{capital.buying_power_pct:.4f}",
                limit=f"{self.policy.maximum_buying_power_pct:.4f}",
                message="Estimated buying power must fit policy.",
            ),
            TradeValidationCheckProfile(
                name="REWARD_RISK",
                passed=(
                    blueprint.reward_risk_ratio
                    >= self.policy.minimum_reward_risk_ratio
                ),
                severity="WARNING",
                actual=f"{blueprint.reward_risk_ratio:.4f}",
                limit=f"{self.policy.minimum_reward_risk_ratio:.4f}",
                message="Reward/risk must meet the minimum.",
            ),
            TradeValidationCheckProfile(
                name="PROBABILITY_OF_PROFIT",
                passed=(
                    blueprint.probability_of_profit
                    >= self.policy.minimum_probability_of_profit
                ),
                severity="WARNING",
                actual=f"{blueprint.probability_of_profit:.4f}",
                limit=f"{self.policy.minimum_probability_of_profit:.4f}",
                message="Probability of profit must meet policy.",
            ),
            TradeValidationCheckProfile(
                name="BID_ASK_SPREAD",
                passed=(
                    worst_spread
                    <= self.policy.maximum_bid_ask_spread_pct
                ),
                severity="WARNING",
                actual=f"{worst_spread:.4f}",
                limit=(
                    f"{self.policy.maximum_bid_ask_spread_pct:.4f}"
                ),
                message="Every leg must satisfy spread policy.",
            ),
            TradeValidationCheckProfile(
                name="OPEN_INTEREST",
                passed=minimum_oi >= self.policy.minimum_open_interest,
                severity="WARNING",
                actual=str(minimum_oi),
                limit=str(self.policy.minimum_open_interest),
                message="Every leg must satisfy open-interest policy.",
            ),
            TradeValidationCheckProfile(
                name="OPTION_VOLUME",
                passed=minimum_volume >= self.policy.minimum_option_volume,
                severity="WARNING",
                actual=str(minimum_volume),
                limit=str(self.policy.minimum_option_volume),
                message="Every leg must satisfy volume policy.",
            ),
        )

    def construct(
        self,
        *,
        symbol: str,
        strategy_name: str,
        direction: str,
        legs: Iterable[Any],
        account_equity: float,
        maximum_profit_per_contract: float | None,
        maximum_loss_per_contract: float | None,
        probability_of_profit: float,
        breakeven_points: Iterable[float] = (),
        quantity_ratios: Iterable[int] | None = None,
        requested_contracts: int | None = None,
    ) -> TradeConstructionProfile:
        blueprint = self._blueprint(
            symbol=symbol,
            strategy_name=strategy_name,
            direction=direction,
            leg_sources=legs,
            quantity_ratios=quantity_ratios,
            maximum_profit_per_contract=maximum_profit_per_contract,
            maximum_loss_per_contract=maximum_loss_per_contract,
            probability_of_profit=probability_of_profit,
            breakeven_points=breakeven_points,
        )
        capital = self._capital(
            blueprint=blueprint,
            account_equity=account_equity,
            requested_contracts=requested_contracts,
        )
        checks = self._checks(blueprint, capital)

        rejection_reasons = tuple(
            check.message
            for check in checks
            if not check.passed and check.severity == "ERROR"
        )
        warnings = tuple(
            check.message
            for check in checks
            if not check.passed and check.severity == "WARNING"
        )
        passed = sum(1 for check in checks if check.passed)
        score = round(100.0 * passed / len(checks), 6)
        allowed = not rejection_reasons
        ticket_status = (
            "READY"
            if allowed and not warnings
            else "READY_WITH_WARNINGS"
            if allowed
            else "REJECTED"
        )
        contracts = capital.recommended_contracts
        multiplier = self.policy.contract_multiplier
        entry_value = (
            blueprint.net_limit_price * multiplier * contracts
        )
        ticket = TradeTicketProfile(
            symbol=symbol,
            strategy_name=strategy_name,
            contracts=contracts,
            order_type=blueprint.order_type,
            time_in_force=blueprint.time_in_force,
            net_limit_price=blueprint.net_limit_price,
            estimated_entry_value=round(entry_value, 6),
            maximum_profit=(
                None
                if blueprint.maximum_profit_per_contract is None
                else round(
                    blueprint.maximum_profit_per_contract
                    * contracts,
                    6,
                )
            ),
            maximum_loss=(
                None
                if blueprint.maximum_loss_per_contract is None
                else round(
                    blueprint.maximum_loss_per_contract
                    * contracts,
                    6,
                )
            ),
            estimated_buying_power=capital.estimated_buying_power,
            legs=blueprint.legs,
            ticket_status=ticket_status,
            executable=allowed and contracts > 0,
        )

        return TradeConstructionProfile(
            blueprint=blueprint,
            capital=capital,
            checks=checks,
            ticket=ticket,
            construction_score=score,
            construction_grade=self._grade(score),
            risk_severity=self._severity(
                len(rejection_reasons),
                len(warnings),
            ),
            allowed=allowed,
            warnings=warnings,
            rejection_reasons=rejection_reasons,
            metadata={
                "milestone": 34,
                "phase": 3,
                "step": 1,
                "source": "STRATEGY_BLUEPRINT_TRADE_TICKET",
            },
        )
