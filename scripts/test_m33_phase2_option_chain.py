from datetime import date
from types import SimpleNamespace

from trading_ai.ui.models.option_chain import OptionChainQuery
from trading_ai.ui.services.option_chain_service import (
    InstitutionalOptionChainService,
    _black_scholes_greeks,
)


class Result:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar
    def all(self):
        return self._rows
    def scalar_one_or_none(self):
        return self._scalar
    def mappings(self):
        return self


class Session:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, statement, params=None):
        sql = str(statement)
        if "SELECT DISTINCT expiry" in sql:
            return Result(rows=[(date(2026, 8, 21),)])
        if "max(quote_date)" in sql:
            return Result(scalar=date(2026, 7, 17))
        if "SELECT close FROM price_history" in sql:
            return Result(scalar=200.0)
        return Result(rows=[
            {
                "underlying_symbol":"AAPL","expiry":date(2026,8,21),
                "quote_date":date(2026,7,17),"strike":200.0,
                "option_type":"CALL","bid":6.0,"ask":6.4,"last":6.2,
                "volume":500,"open_interest":2500,"implied_volatility":0.25,
                "delta":None,"gamma":None,"theta":None,"vega":None,
            },
            {
                "underlying_symbol":"AAPL","expiry":date(2026,8,21),
                "quote_date":date(2026,7,17),"strike":200.0,
                "option_type":"PUT","bid":5.8,"ask":6.2,"last":6.0,
                "volume":400,"open_interest":2200,"implied_volatility":0.26,
                "delta":None,"gamma":None,"theta":None,"vega":None,
            },
        ])


def main():
    delta, gamma, theta, vega = _black_scholes_greeks(
        200, 200, 35/365, 0.04, 0.25, "CALL"
    )
    assert 0 < delta < 1
    assert gamma > 0
    assert theta < 0
    assert vega > 0

    service = InstitutionalOptionChainService(session_factory=Session)
    snapshot = service.snapshot(OptionChainQuery(symbol="AAPL"))
    assert snapshot.symbol == "AAPL"
    assert snapshot.underlying_price == 200.0
    assert len(snapshot.contracts) == 2
    assert len(snapshot.volatility_smile) == 1
    assert snapshot.contracts[0].greek_source == "CALCULATED"
    assert snapshot.put_call_volume_ratio == 0.8
    assert snapshot.put_call_open_interest_ratio == 2200 / 2500

    print(
        "All Milestone 33 Phase 2 Institutional Option Chain, Live Greeks, "
        "Liquidity Ladder, and Volatility Visualization assertions passed."
    )


if __name__ == "__main__":
    main()
