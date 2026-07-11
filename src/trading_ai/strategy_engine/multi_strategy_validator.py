from dataclasses import dataclass, field

from trading_ai.strategy_engine.strategy_catalog import (
    StrategyCatalog,
)
from trading_ai.strategy_engine.strategy_structure import (
    StrategyStructure,
)


@dataclass
class StrategyValidationResult:
    valid: bool

    errors: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )


class MultiStrategyValidator:
    def validate(
        self,
        structure: StrategyStructure,
    ) -> StrategyValidationResult:
        errors = []
        warnings = []

        strategy = structure.strategy
        legs = structure.legs

        if not StrategyCatalog.is_supported(
            strategy
        ):
            errors.append(
                f"Unsupported strategy: {strategy}"
            )

            return StrategyValidationResult(
                valid=False,
                errors=errors,
                warnings=warnings,
            )

        if StrategyCatalog.requires_same_expiry(
            strategy
        ):
            if len(structure.expiries) != 1:
                errors.append(
                    f"{strategy} requires all legs "
                    "to use the same expiry"
                )

        if StrategyCatalog.requires_multiple_expiries(
            strategy
        ):
            if len(structure.expiries) < 2:
                errors.append(
                    f"{strategy} requires at least "
                    "two different expiries"
                )

        expected_leg_count = self._expected_leg_count(
            strategy
        )

        if expected_leg_count is not None:
            if len(legs) != expected_leg_count:
                errors.append(
                    f"{strategy} requires "
                    f"{expected_leg_count} legs; "
                    f"received {len(legs)}"
                )

        self._validate_types(
            structure,
            errors,
        )

        self._validate_actions(
            structure,
            errors,
        )

        self._validate_strikes(
            structure,
            errors,
        )

        self._validate_expiries(
            structure,
            errors,
        )

        if structure.net_debit_per_share <= 0:
            if strategy in {
                "LONG_CALL",
                "LONG_PUT",
                "BULL_CALL_SPREAD",
                "BEAR_PUT_SPREAD",
                "LONG_STRADDLE",
                "LONG_STRANGLE",
                "CALENDAR_CALL",
                "CALENDAR_PUT",
                "DIAGONAL_CALL",
                "DIAGONAL_PUT",
            }:
                warnings.append(
                    f"{strategy} normally opens "
                    "for a net debit"
                )

        if structure.net_credit_per_share <= 0:
            if strategy in {
                "BULL_PUT_SPREAD",
                "BEAR_CALL_SPREAD",
                "IRON_CONDOR",
                "IRON_BUTTERFLY",
            }:
                warnings.append(
                    f"{strategy} normally opens "
                    "for a net credit"
                )

        return StrategyValidationResult(
            valid=not errors,
            errors=errors,
            warnings=warnings,
        )

    def _expected_leg_count(
        self,
        strategy: str,
    ) -> int | None:
        mapping = {
            "LONG_CALL": 1,
            "LONG_PUT": 1,
            "BULL_CALL_SPREAD": 2,
            "BEAR_PUT_SPREAD": 2,
            "BULL_PUT_SPREAD": 2,
            "BEAR_CALL_SPREAD": 2,
            "IRON_CONDOR": 4,
            "IRON_BUTTERFLY": 4,
            "LONG_STRADDLE": 2,
            "LONG_STRANGLE": 2,
            "CALENDAR_CALL": 2,
            "CALENDAR_PUT": 2,
            "DIAGONAL_CALL": 2,
            "DIAGONAL_PUT": 2,
        }

        return mapping.get(strategy)

    def _validate_types(
        self,
        structure,
        errors,
    ):
        strategy = structure.strategy
        types = [
            leg.option_type
            for leg in structure.legs
        ]

        if strategy.endswith("CALL_SPREAD"):
            if any(
                option_type != "CALL"
                for option_type in types
            ):
                errors.append(
                    f"{strategy} requires CALL legs"
                )

        if strategy.endswith("PUT_SPREAD"):
            if any(
                option_type != "PUT"
                for option_type in types
            ):
                errors.append(
                    f"{strategy} requires PUT legs"
                )

        if strategy in {
            "CALENDAR_CALL",
            "DIAGONAL_CALL",
        }:
            if any(
                option_type != "CALL"
                for option_type in types
            ):
                errors.append(
                    f"{strategy} requires CALL legs"
                )

        if strategy in {
            "CALENDAR_PUT",
            "DIAGONAL_PUT",
        }:
            if any(
                option_type != "PUT"
                for option_type in types
            ):
                errors.append(
                    f"{strategy} requires PUT legs"
                )

    def _validate_actions(
        self,
        structure,
        errors,
    ):
        buys = [
            leg
            for leg in structure.legs
            if leg.normalized_action == "BUY"
        ]

        sells = [
            leg
            for leg in structure.legs
            if leg.normalized_action == "SELL"
        ]

        strategy = structure.strategy

        if strategy in {
            "LONG_CALL",
            "LONG_PUT",
        }:
            if len(buys) != 1:
                errors.append(
                    f"{strategy} requires one BUY leg"
                )

        if strategy in {
            "BULL_CALL_SPREAD",
            "BEAR_PUT_SPREAD",
            "BULL_PUT_SPREAD",
            "BEAR_CALL_SPREAD",
            "CALENDAR_CALL",
            "CALENDAR_PUT",
            "DIAGONAL_CALL",
            "DIAGONAL_PUT",
        }:
            if len(buys) != 1 or len(sells) != 1:
                errors.append(
                    f"{strategy} requires one BUY "
                    "and one SELL leg"
                )

        if strategy in {
            "IRON_CONDOR",
            "IRON_BUTTERFLY",
        }:
            if len(buys) != 2 or len(sells) != 2:
                errors.append(
                    f"{strategy} requires two BUY "
                    "and two SELL legs"
                )

        if strategy in {
            "LONG_STRADDLE",
            "LONG_STRANGLE",
        }:
            if len(buys) != 2 or sells:
                errors.append(
                    f"{strategy} requires two BUY legs"
                )

    def _validate_strikes(
        self,
        structure,
        errors,
    ):
        strategy = structure.strategy
        legs = structure.legs

        if strategy == "BULL_CALL_SPREAD":
            long_call = self._buy_leg(legs)
            short_call = self._sell_leg(legs)

            if (
                long_call
                and short_call
                and long_call.strike
                >= short_call.strike
            ):
                errors.append(
                    "BULL_CALL_SPREAD requires "
                    "long strike below short strike"
                )

        if strategy == "BEAR_PUT_SPREAD":
            long_put = self._buy_leg(legs)
            short_put = self._sell_leg(legs)

            if (
                long_put
                and short_put
                and long_put.strike
                <= short_put.strike
            ):
                errors.append(
                    "BEAR_PUT_SPREAD requires "
                    "long strike above short strike"
                )

        if strategy == "BULL_PUT_SPREAD":
            short_put = self._sell_leg(legs)
            long_put = self._buy_leg(legs)

            if (
                short_put
                and long_put
                and short_put.strike
                <= long_put.strike
            ):
                errors.append(
                    "BULL_PUT_SPREAD requires "
                    "short strike above long strike"
                )

        if strategy == "BEAR_CALL_SPREAD":
            short_call = self._sell_leg(legs)
            long_call = self._buy_leg(legs)

            if (
                short_call
                and long_call
                and short_call.strike
                >= long_call.strike
            ):
                errors.append(
                    "BEAR_CALL_SPREAD requires "
                    "short strike below long strike"
                )

        if strategy == "LONG_STRADDLE":
            if len(set(structure.strikes)) != 1:
                errors.append(
                    "LONG_STRADDLE requires "
                    "matching call and put strikes"
                )

        if strategy == "LONG_STRANGLE":
            if len(set(structure.strikes)) != 2:
                errors.append(
                    "LONG_STRANGLE requires "
                    "different call and put strikes"
                )

        if strategy in {
            "CALENDAR_CALL",
            "CALENDAR_PUT",
        }:
            if len(set(structure.strikes)) != 1:
                errors.append(
                    f"{strategy} requires matching strikes"
                )

        if strategy in {
            "DIAGONAL_CALL",
            "DIAGONAL_PUT",
        }:
            if len(set(structure.strikes)) < 2:
                errors.append(
                    f"{strategy} requires different strikes"
                )

    def _validate_expiries(
        self,
        structure,
        errors,
    ):
        strategy = structure.strategy

        if strategy not in {
            "CALENDAR_CALL",
            "CALENDAR_PUT",
            "DIAGONAL_CALL",
            "DIAGONAL_PUT",
        }:
            return

        buy_leg = self._buy_leg(
            structure.legs
        )

        sell_leg = self._sell_leg(
            structure.legs
        )

        if not buy_leg or not sell_leg:
            return

        if buy_leg.expiry <= sell_leg.expiry:
            errors.append(
                f"{strategy} requires the BUY leg "
                "to expire after the SELL leg"
            )

    def _buy_leg(self, legs):
        return next(
            (
                leg
                for leg in legs
                if leg.normalized_action == "BUY"
            ),
            None,
        )

    def _sell_leg(self, legs):
        return next(
            (
                leg
                for leg in legs
                if leg.normalized_action == "SELL"
            ),
            None,
        )
