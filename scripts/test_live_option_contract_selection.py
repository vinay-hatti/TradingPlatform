from datetime import date

from trading_ai.options.live_contract_selector import (
    LiveContractSelectionPolicy,
    LiveOptionContractSelector,
)
from trading_ai.options.live_snapshot import LiveOptionContract


class FakeProvider:
    def chain(self, *args, **kwargs):
        return [
            LiveOptionContract(
                underlying="JPM",
                contract_ticker="O:JPM260814C00345000",
                contract_type="call",
                expiration_date="2026-08-14",
                strike=345.0,
                dte=28,
                bid=5.10,
                ask=5.30,
                midpoint=5.20,
                last_price=5.15,
                entry_price=5.20,
                price_source="NBBO_MIDPOINT",
                delta=0.47,
                gamma=0.02,
                theta=-0.11,
                vega=0.32,
                rho=0.0,
                implied_volatility=0.28,
                open_interest=1200,
                volume=300,
                quote_timestamp=(
                    "2026-07-17T20:00:00+00:00"
                ),
                data_source="POLYGON_OPTION_SNAPSHOT",
                spread_pct=0.03846,
            ),
            LiveOptionContract(
                underlying="JPM",
                contract_ticker="O:JPM260814C00350000",
                contract_type="call",
                expiration_date="2026-08-14",
                strike=350.0,
                dte=28,
                bid=3.90,
                ask=4.40,
                midpoint=4.15,
                last_price=4.10,
                entry_price=4.15,
                price_source="NBBO_MIDPOINT",
                delta=0.39,
                gamma=0.02,
                theta=-0.10,
                vega=0.31,
                rho=0.0,
                implied_volatility=0.29,
                open_interest=800,
                volume=200,
                quote_timestamp=(
                    "2026-07-17T20:00:00+00:00"
                ),
                data_source="POLYGON_OPTION_SNAPSHOT",
                spread_pct=0.12048,
            ),
        ]


def main():
    selector = LiveOptionContractSelector(
        provider=FakeProvider(),
        policy=LiveContractSelectionPolicy(
            target_abs_delta=0.45,
            maximum_spread_pct=0.35,
        ),
    )
    selected = selector.select(
        underlying="JPM",
        signal="CALL",
        target_expiration=date(2026, 8, 14),
        target_strike=345.0,
        as_of=date(2026, 7, 17),
    )
    assert (
        selected.contract_ticker
        == "O:JPM260814C00345000"
    )
    assert selected.entry_price == 5.20
    assert selected.delta == 0.47
    assert selected.price_source == "NBBO_MIDPOINT"
    print(
        "All live option contract-selection assertions passed."
    )


if __name__ == "__main__":
    main()
