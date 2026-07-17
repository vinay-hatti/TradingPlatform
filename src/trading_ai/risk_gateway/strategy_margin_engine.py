from __future__ import annotations
from collections import defaultdict
from .options_risk_policy import OptionsRiskPolicy
from .options_risk_profile import OptionGreekProfile, StrategyMarginProfile
from .pretrade_risk_profile import PreTradeAccountProfile

def _signed_premium(leg: OptionGreekProfile) -> float:
    direction = -1.0 if leg.side.upper().startswith("SELL") else 1.0
    return direction * abs(leg.quantity) * float(leg.option_price or 0.0) * max(int(leg.multiplier or 1), 1)

class StrategyMarginEngine:
    def __init__(self, policy: OptionsRiskPolicy | None = None) -> None:
        self.policy = policy or OptionsRiskPolicy()
        self.policy.validate()

    def evaluate(
        self,
        legs: tuple[OptionGreekProfile, ...],
        account: PreTradeAccountProfile | None,
    ) -> StrategyMarginProfile:
        if not legs:
            return StrategyMarginProfile(
                strategy_classification="NO_OPTION_LEGS",
                defined_risk=True,
                uncovered_short_option=False,
                maximum_loss=0.0,
                margin_required=0.0,
                margin_utilization=0.0,
            )

        net_premium = sum(_signed_premium(leg) for leg in legs)
        long_legs = [leg for leg in legs if leg.side.upper().startswith("BUY")]
        short_legs = [leg for leg in legs if leg.side.upper().startswith("SELL")]

        if len(legs) == 1:
            leg = legs[0]
            if leg.side.upper().startswith("BUY"):
                max_loss = abs(net_premium)
                margin = max_loss
                classification = "DEFINED_RISK_LONG_OPTION"
                defined = True
                uncovered = False
                width = None
            else:
                underlying_price = float(leg.underlying_price or 0.0)
                strike = float(leg.strike or underlying_price)
                multiplier = max(int(leg.multiplier or 1), 1)
                quantity = abs(float(leg.quantity))
                base = max(0.20 * underlying_price - max(0.0, strike - underlying_price), 0.10 * underlying_price)
                margin = quantity * multiplier * (base + float(leg.option_price or 0.0))
                max_loss = None
                classification = "UNDEFINED_RISK_SHORT_OPTION"
                defined = False
                uncovered = True
                width = None
        else:
            grouped = defaultdict(list)
            for leg in legs:
                key = (
                    leg.underlying_symbol,
                    leg.expiration,
                    str(leg.option_type or "").upper(),
                )
                grouped[key].append(leg)

            vertical_widths = []
            all_defined = True
            for group_legs in grouped.values():
                group_longs = [leg for leg in group_legs if leg.side.upper().startswith("BUY")]
                group_shorts = [leg for leg in group_legs if leg.side.upper().startswith("SELL")]
                if not group_longs or not group_shorts:
                    all_defined = False
                    continue
                strikes = [
                    float(leg.strike)
                    for leg in group_legs
                    if leg.strike is not None
                ]
                if len(strikes) < 2:
                    all_defined = False
                    continue
                vertical_widths.append(max(strikes) - min(strikes))

            if all_defined and vertical_widths:
                width = max(vertical_widths)
                contracts = max(abs(float(leg.quantity)) for leg in legs)
                multiplier = max(int(leg.multiplier or 1) for leg in legs)
                spread_risk = width * contracts * multiplier
                max_loss = max(0.0, spread_risk + max(net_premium, 0.0))
                margin = max_loss
                classification = "DEFINED_RISK_VERTICAL_SPREAD"
                defined = True
                uncovered = False
            elif short_legs:
                margin = 0.0
                for leg in short_legs:
                    underlying_price = float(leg.underlying_price or 0.0)
                    strike = float(leg.strike or underlying_price)
                    multiplier = max(int(leg.multiplier or 1), 1)
                    quantity = abs(float(leg.quantity))
                    base = max(0.20 * underlying_price - max(0.0, strike - underlying_price), 0.10 * underlying_price)
                    margin += quantity * multiplier * (base + float(leg.option_price or 0.0))
                max_loss = None
                width = None
                classification = "UNDEFINED_RISK_MULTI_LEG_OPTION"
                defined = False
                uncovered = True
            else:
                max_loss = abs(net_premium)
                margin = max_loss
                width = None
                classification = "DEFINED_RISK_MULTI_LONG_OPTION"
                defined = True
                uncovered = False

        buying_power = account.buying_power if account is not None else 0.0
        utilization = margin / buying_power if buying_power > 0 else None
        return StrategyMarginProfile(
            strategy_classification=classification,
            defined_risk=defined,
            uncovered_short_option=uncovered,
            maximum_loss=round(max_loss, 6) if max_loss is not None else None,
            margin_required=round(margin, 6),
            margin_utilization=utilization,
            width=round(width, 6) if width is not None else None,
            net_premium=round(net_premium, 6),
        )
