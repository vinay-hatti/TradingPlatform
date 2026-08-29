from datetime import date
import math

from trading_ai.options.live_contract_selector import (
    LiveContractSelectionPolicy,
    LiveOptionContractSelector,
)
from trading_ai.options.live_snapshot import LiveOptionContract


AS_OF = date(2026, 7, 24)
EXPIRY = date(2026, 9, 18)


def contract(
    ticker,
    *,
    bid,
    ask,
    last,
    open_interest=1000,
    volume=100,
    expiration=EXPIRY,
):
    midpoint = (bid + ask) / 2.0 if bid > 0 and ask >= bid else 0.0
    spread_pct = (
        (ask - bid) / midpoint if midpoint > 0 else math.inf
    )
    return LiveOptionContract(
        underlying="TEST",
        contract_ticker=ticker,
        contract_type="call",
        expiration_date=expiration.isoformat(),
        strike=100.0,
        dte=(expiration - AS_OF).days,
        bid=bid,
        ask=ask,
        midpoint=midpoint,
        last_price=last,
        entry_price=midpoint or last,
        price_source="POLYGON_PERSISTED_QUOTE",
        delta=0.45,
        gamma=0.02,
        theta=-0.03,
        vega=0.15,
        rho=0.0,
        implied_volatility=0.25,
        open_interest=open_interest,
        volume=volume,
        quote_timestamp="2026-07-23",
        data_source="POLYGON_PERSISTED",
        spread_pct=spread_pct,
    )


class Provider:
    def __init__(self, contracts):
        self.contracts = contracts

    def chain(self, *args, **kwargs):
        return list(self.contracts)


def main():
    tight = contract("O:TIGHT", bid=4.90, ask=5.10, last=5.00)
    last_only = contract("O:LAST", bid=0.0, ask=0.0, last=5.00)

    selector = LiveOptionContractSelector(
        provider=Provider([last_only, tight]),
        policy=LiveContractSelectionPolicy(
            liquidity_data_mode="adaptive",
            minimum_open_interest=1,
            minimum_volume=1,
            maximum_spread_pct=0.25,
        ),
    )
    ranked = selector.rank(
        underlying="TEST",
        signal="CALL",
        target_expiration=EXPIRY,
        target_strike=100.0,
        as_of=AS_OF,
    )

    assert ranked[0].contract_ticker == "O:TIGHT"
    assert ranked[0].entry_price == 5.0
    assert ranked[0].score.spread_available is True
    assert ranked[0].score.spread_score > ranked[1].score.spread_score
    assert ranked[1].score.spread_available is False

    wide = contract("O:WIDE", bid=4.0, ask=6.0, last=5.0)
    strict_selector = LiveOptionContractSelector(
        provider=Provider([wide]),
        policy=LiveContractSelectionPolicy(
            liquidity_data_mode="strict",
            minimum_open_interest=1,
            minimum_volume=1,
            maximum_spread_pct=0.25,
        ),
    )
    try:
        strict_selector.rank(
            underlying="TEST",
            signal="CALL",
            target_expiration=EXPIRY,
            target_strike=100.0,
            as_of=AS_OF,
        )
    except Exception as exc:
        assert "wide_spread=1" in str(exc)
    else:
        raise AssertionError("Wide-spread contract should be rejected")

    near_expiry = contract(
        "O:NEAR",
        bid=4.90,
        ask=5.10,
        last=5.00,
        expiration=EXPIRY,
    )
    farther_expiry = contract(
        "O:FAR",
        bid=4.90,
        ask=5.10,
        last=5.00,
        expiration=date(2026, 9, 25),
    )
    curve_selector = LiveOptionContractSelector(
        provider=Provider([farther_expiry, near_expiry]),
        policy=LiveContractSelectionPolicy(
            liquidity_data_mode="adaptive",
            minimum_open_interest=1,
            minimum_volume=1,
            expiration_window_days=10,
        ),
    )
    curve_ranked = curve_selector.rank(
        underlying="TEST",
        signal="CALL",
        target_expiration=EXPIRY,
        target_strike=100.0,
        as_of=AS_OF,
    )
    assert curve_ranked[0].contract_ticker == "O:NEAR"
    assert (
        curve_ranked[0].score.expiration_score
        > curve_ranked[1].score.expiration_score
    )

    print("Daily scanner quote-aware contract ranking assertions passed.")


if __name__ == "__main__":
    main()
