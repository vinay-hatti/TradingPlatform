from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace
import importlib.util
import sys

config_module = ModuleType("trading_ai.config")
config_module.settings = SimpleNamespace(polygon_api_key="test")
sys.modules["trading_ai.config"] = config_module

@dataclass
class MarketBar:
    symbol: str
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float

dto_module = ModuleType("trading_ai.market.dto")
dto_module.MarketBar = MarketBar
sys.modules["trading_ai.market.dto"] = dto_module

path = Path(__file__).parents[1] / "payload/src/trading_ai/market/providers/polygon.py"
spec = importlib.util.spec_from_file_location("optimized_polygon_provider", path)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
PolygonHistoricalProvider = module.PolygonHistoricalProvider

class FakeClient:
    def get_grouped_daily_aggs(self, **kwargs):
        return [
            SimpleNamespace(ticker="AAPL", timestamp=1722211200000, open=100, high=102, low=99, close=101, volume=1000),
            SimpleNamespace(ticker="MSFT", timestamp=1722211200000, open=200, high=202, low=198, close=201, volume=2000),
            SimpleNamespace(ticker="OTHER", timestamp=1722211200000, open=10, high=11, low=9, close=10.5, volume=50),
        ]

def main():
    provider = PolygonHistoricalProvider({"AAPL": "AAPL", "MSFT": "MSFT"}, api_key="test", client=FakeClient())
    bars = provider.fetch_grouped_daily(date(2026, 7, 29), symbols=("AAPL", "MSFT"))
    assert [bar.symbol for bar in bars] == ["AAPL", "MSFT"]
    print("Polygon grouped OHLCV optimization assertions passed.")

if __name__ == "__main__":
    main()
