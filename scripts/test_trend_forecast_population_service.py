from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from datetime import date

import pandas as pd

# The package imports the repository's normal SessionLocal at module import time.
# Provide a harmless stub so this isolated regression test can run outside the
# full TradingPlatform repository; the service is then injected with its fake
# session factory below.
session_module = types.ModuleType("trading_ai.database.session")
session_module.SessionLocal = lambda: None
database_module = types.ModuleType("trading_ai.database")
sys.modules.setdefault("trading_ai.database", database_module)
sys.modules.setdefault("trading_ai.database.session", session_module)

from trading_ai.trend_intelligence.forecast_service import TrendForecastService


class _Row:
    def __init__(self, mapping):
        self._mapping = mapping


class _Session:
    def execute(self, _sql, params):
        assert params["symbols"] == ["AAPL"]
        dates = pd.bdate_range("2025-01-02", periods=140)
        return [
            _Row(
                {
                    "symbol": "AAPL",
                    "date": value.date(),
                    "close": 100.0 + index * 0.25,
                    "volume": 1_000_000 + index,
                }
            )
            for index, value in enumerate(dates)
        ]


class _Repository:
    def __init__(self):
        self.saved = []

    def save(self, snapshot):
        self.saved.append(snapshot)


@contextmanager
def _session_factory():
    yield _Session()


def main() -> None:
    repository = _Repository()
    service = TrendForecastService(
        session_factory=_session_factory,
        repository=repository,
    )
    result = service.run(
        symbols=["AAPL"],
        start="2025-01-01",
        end="2026-07-28",
        report_path="/tmp/test_trend_forecasts_latest.json",
    )
    assert result["status"] == "READY", result
    assert result["symbol_count"] == 1, result
    assert result["forecast_count"] == 3, result
    assert result["error_count"] == 0, result
    assert len(repository.saved) == 3
    expected_as_of = str(date(2025, 7, 16))
    assert all(item.as_of_date == expected_as_of for item in repository.saved)
    print("All Trend Forecast population service assertions passed.")


if __name__ == "__main__":
    main()
