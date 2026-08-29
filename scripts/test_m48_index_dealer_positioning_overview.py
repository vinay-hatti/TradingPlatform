from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

database_module = types.ModuleType("trading_ai.database")
database_module.SessionLocal = object()
sys.modules["trading_ai.database"] = database_module

contracts_module = types.ModuleType("trading_ai.market_overview.contracts")
contracts_module.MarketOverviewSnapshot = object
sys.modules["trading_ai.market_overview.contracts"] = contracts_module

from trading_ai.market_overview.service import MarketOverviewService


class _Mappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _Mappings(self._rows)


class _Session:
    def __init__(self, rows):
        self.rows = rows
        self.parameters = None
        self.rolled_back = False

    def execute(self, _statement, parameters):
        self.parameters = parameters
        return _Result(self.rows)

    def rollback(self):
        self.rolled_back = True


rows = [
    {
        "symbol": "I:SPX",
        "as_of_date": date(2026, 7, 25),
        "quote_date": date(2026, 7, 25),
        "spot_price": 6400.0,
        "gamma_regime": "POSITIVE_GAMMA",
        "gamma_flip": 6350.0,
        "primary_call_wall": 6500.0,
        "primary_put_wall": 6250.0,
        "magnet_strike": 6400.0,
        "expected_move_pct": 0.012,
        "atm_iv": 0.14,
        "iv_term_slope": 0.01,
        "put_skew": 0.03,
        "call_skew": -0.01,
        "institutional_positioning_score": 72.0,
        "positioning_label": "BULLISH",
        "bull_probability": 0.62,
        "bear_probability": 0.18,
        "range_probability": 0.55,
        "breakout_probability": 0.30,
        "breakdown_probability": 0.15,
        "volatility_expansion_probability": 0.38,
        "volatility_compression_probability": 0.62,
        "confidence_score": 0.84,
        "net_gamma_exposure": 100.0,
        "net_delta_exposure": 200.0,
        "net_vanna_exposure": 50.0,
        "net_charm_exposure": 25.0,
        "quote_coverage_pct": 0.91,
    },
    {**{}, **{
        "symbol": "I:NDX", "as_of_date": date(2026, 7, 25), "quote_date": date(2026, 7, 25),
        "spot_price": 23000.0, "gamma_regime": "NEGATIVE_GAMMA", "gamma_flip": 22800.0,
        "primary_call_wall": 23500.0, "primary_put_wall": 22000.0, "magnet_strike": 23000.0,
        "expected_move_pct": 0.016, "atm_iv": 0.18, "iv_term_slope": 0.02, "put_skew": 0.04,
        "call_skew": -0.01, "institutional_positioning_score": 61.0, "positioning_label": "NEUTRAL",
        "bull_probability": 0.45, "bear_probability": 0.30, "range_probability": 0.42,
        "breakout_probability": 0.38, "breakdown_probability": 0.20,
        "volatility_expansion_probability": 0.60, "volatility_compression_probability": 0.40,
        "confidence_score": 0.78, "net_gamma_exposure": -50.0, "net_delta_exposure": 90.0,
        "net_vanna_exposure": 20.0, "net_charm_exposure": 10.0, "quote_coverage_pct": 0.88,
    }},
    {**{}, **{
        "symbol": "RTY", "as_of_date": date(2026, 7, 25), "quote_date": date(2026, 7, 25),
        "spot_price": 2200.0, "gamma_regime": "POSITIVE_GAMMA", "gamma_flip": 2175.0,
        "primary_call_wall": 2250.0, "primary_put_wall": 2100.0, "magnet_strike": 2200.0,
        "expected_move_pct": 0.019, "atm_iv": 0.21, "iv_term_slope": 0.03, "put_skew": 0.05,
        "call_skew": -0.02, "institutional_positioning_score": 58.0, "positioning_label": "NEUTRAL",
        "bull_probability": 0.40, "bear_probability": 0.32, "range_probability": 0.50,
        "breakout_probability": 0.28, "breakdown_probability": 0.22,
        "volatility_expansion_probability": 0.48, "volatility_compression_probability": 0.52,
        "confidence_score": 0.73, "net_gamma_exposure": 40.0, "net_delta_exposure": 70.0,
        "net_vanna_exposure": 15.0, "net_charm_exposure": 8.0, "quote_coverage_pct": 0.82,
    }},
]

session = _Session(rows)
service = MarketOverviewService(session_factory=None)
resolved = service._dealer(session, ["SPX", "NDX", "RUT", "SPY"])

assert set(resolved) == {"SPX", "NDX", "RUT"}
assert resolved["SPX"]["symbol"] == "SPX"
assert resolved["SPX"]["source_symbol"] == "I:SPX"
assert resolved["NDX"]["source_symbol"] == "I:NDX"
assert resolved["RUT"]["symbol"] == "RUT"
assert resolved["RUT"]["source_symbol"] == "RTY"
assert "I:SPX" in session.parameters["symbols"]
assert "I:NDX" in session.parameters["symbols"]
assert "I:RUT" in session.parameters["symbols"]
assert "RTY" in session.parameters["symbols"]
assert not session.rolled_back

print("Milestone 48 index dealer-positioning overview assertions passed.")
