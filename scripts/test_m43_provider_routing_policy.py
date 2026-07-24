from pathlib import Path

from trading_ai.market.provider_routing import DataCapability, ProviderRoutingPolicy
from trading_ai.market.service import MarketService
from trading_ai.market.providers.yahoo import YahooHistoricalProvider
from trading_ai.options.chain import OptionChain


class FakePolygonOptions:
    name = "polygon"
    def get_chain(self, symbol):
        return []


class FakeYahooOptions:
    name = "yahoo"
    def get_chain(self, symbol):
        return []


assert ProviderRoutingPolicy.route(DataCapability.UNDERLYING_OHLCV).primary_provider == "yahoo"
assert ProviderRoutingPolicy.route(DataCapability.UNDERLYING_OHLCV).fallback_provider is None
for capability in (
    DataCapability.OPTION_CHAIN,
    DataCapability.OPTION_QUOTES,
    DataCapability.OPTION_GREEKS,
    DataCapability.OPTION_OPEN_INTEREST,
    DataCapability.OPTION_VOLUME,
):
    route = ProviderRoutingPolicy.route(capability)
    assert route.primary_provider == "polygon"
    assert route.fallback_provider is None

service = MarketService(provider=YahooHistoricalProvider())
assert service.provider.name == "yahoo"
OptionChain(provider=FakePolygonOptions())
try:
    OptionChain(provider=FakeYahooOptions())
except ValueError as exc:
    assert "Provider policy violation" in str(exc)
else:
    raise AssertionError("Yahoo options provider must be rejected")

chain_source = Path("src/trading_ai/options/chain.py").read_text()
assert "yfinance" not in chain_source
market_source = Path("src/trading_ai/market/service.py").read_text()
assert "providers.polygon" not in market_source
print("Milestone 43 provider routing policy assertions passed.")
