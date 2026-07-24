from __future__ import annotations

from collections import defaultdict
from typing import Any

from trading_ai.market.provider_routing import DataCapability, ProviderRoutingPolicy
from trading_ai.options.providers.polygon import PolygonOptionsProvider


class OptionChain:
    """Polygon-only option-chain facade.

    Yahoo options access is intentionally prohibited by provider governance.
    """

    def __init__(self, provider: Any | None = None) -> None:
        self.provider = provider or PolygonOptionsProvider()
        provider_name = str(getattr(self.provider, "name", "polygon")).lower()
        ProviderRoutingPolicy.assert_provider(DataCapability.OPTION_CHAIN, provider_name)

    def _contracts(self, symbol: str):
        return list(self.provider.get_chain(symbol.upper().strip()))

    def get_chain(self, symbol: str, expiration: str):
        grouped = defaultdict(list)
        for contract in self._contracts(symbol):
            if str(contract.expiry) != str(expiration):
                continue
            option_type = str(contract.option_type).upper()
            grouped["calls" if option_type in {"CALL", "C"} else "puts"].append(contract)
        return {"calls": grouped["calls"], "puts": grouped["puts"]}

    def expirations(self, symbol: str):
        return sorted({str(contract.expiry) for contract in self._contracts(symbol)})
