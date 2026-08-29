from datetime import date

import pytest

from trading_ai.option_valuation_intelligence.engine import (
    InstitutionalOptionValuationEngine,
)
from trading_ai.option_valuation_intelligence.market_inputs import (
    MarketInputValidationError,
    resolve_coherent_market_inputs,
)


PSX_CONTRACT = {
    "strategy": "BULL_CALL_SPREAD",
    "legs": [
        {
            "side": "BUY",
            "option_type": "CALL",
            "option_symbol": "O:PSX260918C00200000",
            "expiry": "2026-09-18",
            "strike": 200,
            "bid": 10.0,
            "ask": 10.9,
        },
        {
            "side": "SELL",
            "option_type": "CALL",
            "option_symbol": "O:PSX260918C00220000",
            "expiry": "2026-09-18",
            "strike": 220,
            "bid": 3.4,
            "ask": 3.9,
        },
    ],
}


def _quote(symbol, quote_date, bid, ask, iv):
    return {
        "option_symbol": symbol,
        "quote_date": quote_date,
        "expiry": date(2026, 9, 18),
        "bid": bid,
        "ask": ask,
        "last": (bid + ask) / 2,
        "implied_volatility": iv,
    }


def test_psx_regression_refreshes_all_legs_and_ignores_weekend_capture_date():
    option_rows = [
        _quote("O:PSX260918C00200000", date(2026, 8, 14), 31.0, 34.0, 0.2691),
        _quote("O:PSX260918C00220000", date(2026, 8, 14), 15.5, 18.6, 0.3107),
        # These legacy rows were captured Saturday without a provider quote
        # timestamp. They cannot be paired with a Saturday underlying close.
        _quote("O:PSX260918C00200000", date(2026, 8, 15), 31.8, 34.9, 0.29),
        _quote("O:PSX260918C00220000", date(2026, 8, 15), 15.5, 18.6, 0.2930),
    ]
    price_rows = [
        {"date": date(2026, 8, 5), "close": 202.55},
        {"date": date(2026, 8, 14), "close": 233.61},
    ]

    resolved = resolve_coherent_market_inputs(
        contract=PSX_CONTRACT,
        option_rows=option_rows,
        price_rows=price_rows,
    )

    assert resolved.market_date == date(2026, 8, 14)
    assert resolved.underlying_price == 233.61
    assert resolved.dte_min == resolved.dte_max == 35
    legs = resolved.payload["legs"]
    package_mid = (legs[0]["bid"] + legs[0]["ask"]) / 2 - (
        legs[1]["bid"] + legs[1]["ask"]
    ) / 2
    assert package_mid == pytest.approx(15.45)
    assert package_mid != pytest.approx(7.10)
    assert resolved.payload["market_input_validation"]["status"] == "CURRENT_COHERENT"


def test_missing_current_leg_fails_closed_instead_of_mixing_dates():
    with pytest.raises(MarketInputValidationError) as error:
        resolve_coherent_market_inputs(
            contract=PSX_CONTRACT,
            option_rows=[
                _quote("O:PSX260918C00200000", date(2026, 8, 14), 31.0, 34.0, 0.2691),
                _quote("O:PSX260918C00220000", date(2026, 8, 13), 15.1, 18.0, 0.3108),
            ],
            price_rows=[{"date": date(2026, 8, 14), "close": 233.61}],
        )
    assert error.value.code == "NO_COHERENT_MARKET_DATE"


def test_provider_timestamp_and_source_spot_support_current_intraday_snapshot():
    option_rows = [
        _quote("O:PSX260918C00200000", date(2026, 8, 17), 32.0, 33.0, 0.27)
        | {"quote_timestamp": "2026-08-17T18:30:00Z", "source_underlying_price": 234.10},
        _quote("O:PSX260918C00220000", date(2026, 8, 17), 16.0, 17.0, 0.30)
        | {"quote_timestamp": "2026-08-17T18:30:01Z", "source_underlying_price": 234.12},
    ]
    resolved = resolve_coherent_market_inputs(
        contract=PSX_CONTRACT,
        option_rows=option_rows,
        price_rows=[{"date": date(2026, 8, 14), "close": 233.61}],
    )
    assert resolved.market_date == date(2026, 8, 17)
    assert resolved.underlying_price == pytest.approx(234.11)
    assert (
        resolved.payload["market_input_validation"]["underlying_price_source"]
        == "POLYGON_SNAPSHOT"
    )


def test_diagonal_engine_uses_each_legs_own_dte():
    contract = {
        "strategy": "CALL_DIAGONAL",
        "underlying_price": 100.0,
        "market_input_as_of": "2026-08-14",
        "underlying_price_as_of": "2026-08-14",
        "quote_input_snapshot_id": "coherent-options-2026-08-14",
        "market_input_validation": {"status": "CURRENT_COHERENT"},
        "legs": [
            {
                "side": "BUY", "option_type": "CALL", "option_symbol": "FAR",
                "strike": 100.0, "dte": 65, "bid": 8.0, "ask": 8.4,
                "implied_volatility": 0.30,
            },
            {
                "side": "SELL", "option_type": "CALL", "option_symbol": "NEAR",
                "strike": 105.0, "dte": 23, "bid": 2.5, "ask": 2.8,
                "implied_volatility": 0.31,
            },
        ],
    }
    result = InstitutionalOptionValuationEngine().evaluate(
        opportunity={"direction": "BULLISH"}, contract=contract
    )
    assert result["dte"] == 23
    assert result["dte_min"] == 23
    assert result["dte_max"] == 65
    assert result["per_leg_dte"] == {"FAR": 65, "NEAR": 23}
