from pathlib import Path
from types import SimpleNamespace

from trading_ai.market.provider_routing import DataCapability, ProviderRoutingPolicy
from trading_ai.market.service import MarketService
from trading_ai.market.providers.polygon import PolygonHistoricalProvider
from trading_ai.options.chain import OptionChain


class FakePolygonOptions:
    name = "polygon"
    def get_chain(self, symbol): return []

class FakeOtherOptions:
    name = "other"
    def get_chain(self, symbol): return []

class FakePolygonHistory:
    name = "polygon"
    def fetch_history(self, symbol, start, end): return []

assert ProviderRoutingPolicy.route(DataCapability.UNDERLYING_OHLCV).primary_provider == "polygon"
assert ProviderRoutingPolicy.route(DataCapability.UNDERLYING_OHLCV).fallback_provider is None
for capability in DataCapability:
    route=ProviderRoutingPolicy.route(capability)
    assert route.primary_provider == "polygon"
    assert route.fallback_provider is None

service=MarketService(provider=FakePolygonHistory(), session_factory=lambda: None)
assert service.provider.name == "polygon"
OptionChain(provider=FakePolygonOptions())
try:
    OptionChain(provider=FakeOtherOptions())
except ValueError as exc:
    assert "Provider policy violation" in str(exc)
else:
    raise AssertionError("Non-Polygon options provider must be rejected")

chain_source=Path("src/trading_ai/options/chain.py").read_text()
assert "polygon" in chain_source.lower()
market_source=Path("src/trading_ai/market/service.py").read_text()
assert "providers.polygon" in market_source
print("Milestone 43 Polygon-only provider routing policy assertions passed.")
