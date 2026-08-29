from __future__ import annotations

from datetime import date

from trading_ai.options.live_contract_selector import (
    LiveContractSelectionPolicy,
    LiveOptionContractSelector,
)
from trading_ai.options.live_snapshot import LiveOptionContract


def make_contract(
    ticker,
    delta,
    oi,
    volume,
    spread,
):
    midpoint = 5.0
    half = midpoint * spread / 2.0
    return LiveOptionContract(
        underlying="JPM",
        contract_ticker=ticker,
        contract_type="call",
        expiration_date="2026-08-14",
        strike=345.0,
        dte=28,
        bid=midpoint - half,
        ask=midpoint + half,
        midpoint=midpoint,
        last_price=4.95,
        entry_price=midpoint,
        price_source="NBBO_MIDPOINT",
        delta=delta,
        gamma=0.02,
        theta=-0.10,
        vega=0.30,
        rho=0.0,
        implied_volatility=0.28,
        open_interest=oi,
        volume=volume,
        quote_timestamp="2026-07-17T20:00:00+00:00",
        data_source="POLYGON_OPTION_SNAPSHOT",
        spread_pct=spread,
    )


class FakeProvider:
    def chain(self, *args, **kwargs):
        return [
            make_contract(
                "O:JPM_THIN",
                0.45,
                120,
                12,
                0.24,
            ),
            make_contract(
                "O:JPM_LIQUID",
                0.42,
                8000,
                2500,
                0.03,
            ),
            make_contract(
                "O:JPM_LOW_OI",
                0.45,
                20,
                5000,
                0.02,
            ),
        ]


def main():
    selector = LiveOptionContractSelector(
        provider=FakeProvider(),
        policy=LiveContractSelectionPolicy(
            target_abs_delta=0.45,
            maximum_spread_pct=0.25,
            minimum_open_interest=100,
            minimum_volume=10,
            delta_weight=0.25,
            expiration_weight=0.15,
            strike_weight=0.10,
            spread_weight=0.15,
            open_interest_weight=0.20,
            volume_weight=0.15,
        ),
    )
    ranked = selector.rank(
        underlying="JPM",
        signal="CALL",
        target_expiration=date(2026, 8, 14),
        target_strike=345.0,
        as_of=date(2026, 7, 17),
    )
    assert len(ranked) == 2
    assert ranked[0].contract_ticker == "O:JPM_LIQUID"
    assert ranked[0].score.total_score > ranked[1].score.total_score
    assert all(x.contract_ticker != "O:JPM_LOW_OI" for x in ranked)
    print(
        "Selected:",
        ranked[0].contract_ticker,
        "total=",
        round(ranked[0].score.total_score, 2),
        "liquidity=",
        round(ranked[0].score.liquidity_score, 2),
    )
    print(
        "All liquidity-weighted contract-selection "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
