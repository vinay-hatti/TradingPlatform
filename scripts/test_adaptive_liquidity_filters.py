from datetime import date
from trading_ai.options.live_contract_selector import (
    LiveContractSelectionPolicy, LiveOptionContractSelector
)
from trading_ai.options.live_snapshot import LiveOptionContract

def contract():
    return LiveOptionContract(
        underlying="SPY", contract_ticker="O:SPY_TEST", contract_type="call",
        expiration_date="2026-08-14", strike=700.0, dte=27,
        bid=0.0, ask=0.0, midpoint=0.0, last_price=5.0,
        entry_price=5.0, price_source="LAST_TRADE",
        delta=0.44, gamma=0.02, theta=-0.10, vega=0.30, rho=0.0,
        implied_volatility=0.20, open_interest=0, volume=0,
        quote_timestamp="2026-07-17T20:00:00+00:00",
        data_source="POLYGON_OPTION_SNAPSHOT", spread_pct=float("inf"),
    )

class Provider:
    def chain(self, *args, **kwargs): return [contract()]

def main():
    adaptive = LiveOptionContractSelector(
        provider=Provider(),
        policy=LiveContractSelectionPolicy(liquidity_data_mode="adaptive"),
    )
    selected = adaptive.select(
        underlying="SPY", signal="CALL",
        target_expiration=date(2026,8,14),
        target_strike=700.0, as_of=date(2026,7,18),
    )
    assert selected.contract_ticker == "O:SPY_TEST"
    assert not selected.score.open_interest_available
    assert not selected.score.volume_available
    assert not selected.score.spread_available

    strict = LiveOptionContractSelector(
        provider=Provider(),
        policy=LiveContractSelectionPolicy(liquidity_data_mode="strict"),
    )
    try:
        strict.select(
            underlying="SPY", signal="CALL",
            target_expiration=date(2026,8,14),
            target_strike=700.0, as_of=date(2026,7,18),
        )
    except Exception:
        pass
    else:
        raise AssertionError("strict mode accepted unavailable fields")
    print("All adaptive-liquidity filter assertions passed.")

if __name__ == "__main__":
    main()
