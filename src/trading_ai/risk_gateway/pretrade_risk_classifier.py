from __future__ import annotations

from .pretrade_risk_profile import PreTradeRiskRequest


def classify_option_risk(request: PreTradeRiskRequest) -> tuple[bool, str]:
    option_legs = [
        leg for leg in request.legs
        if leg.asset_class.upper() == "OPTION"
    ]
    if not option_legs:
        return True, "NON_OPTION"

    if len(option_legs) == 1:
        side = option_legs[0].side.upper()
        if side.startswith("BUY"):
            return True, "DEFINED_RISK_LONG_OPTION"
        return False, "UNDEFINED_RISK_SHORT_OPTION"

    underlyings = {
        str(leg.metadata.get("underlying_symbol", leg.symbol)).upper()
        for leg in option_legs
    }
    expirations = {leg.expiration for leg in option_legs}
    buy_legs = [leg for leg in option_legs if leg.side.upper().startswith("BUY")]
    sell_legs = [leg for leg in option_legs if leg.side.upper().startswith("SELL")]

    if len(underlyings) == 1 and len(expirations) == 1 and buy_legs and sell_legs:
        return True, "DEFINED_RISK_OPTION_SPREAD"

    return False, "UNDEFINED_RISK_MULTI_LEG_OPTION"
