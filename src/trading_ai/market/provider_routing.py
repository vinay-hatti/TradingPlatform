from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DataCapability(str, Enum):
    UNDERLYING_OHLCV = "underlying_ohlcv"
    OPTION_CHAIN = "option_chain"
    OPTION_QUOTES = "option_quotes"
    OPTION_GREEKS = "option_greeks"
    OPTION_OPEN_INTEREST = "option_open_interest"
    OPTION_VOLUME = "option_volume"


@dataclass(frozen=True)
class ProviderRoute:
    capability: DataCapability
    primary_provider: str
    fallback_provider: str | None = None


class ProviderRoutingPolicy:
    """Authoritative market-data source governance.

    Yahoo is restricted to underlying OHLCV. Polygon is the sole source for
    option contracts, quotes, Greeks, volume, open interest and IV data.
    """

    _ROUTES = {
        DataCapability.UNDERLYING_OHLCV: ProviderRoute(
            DataCapability.UNDERLYING_OHLCV, "yahoo", None
        ),
        DataCapability.OPTION_CHAIN: ProviderRoute(
            DataCapability.OPTION_CHAIN, "polygon", None
        ),
        DataCapability.OPTION_QUOTES: ProviderRoute(
            DataCapability.OPTION_QUOTES, "polygon", None
        ),
        DataCapability.OPTION_GREEKS: ProviderRoute(
            DataCapability.OPTION_GREEKS, "polygon", None
        ),
        DataCapability.OPTION_OPEN_INTEREST: ProviderRoute(
            DataCapability.OPTION_OPEN_INTEREST, "polygon", None
        ),
        DataCapability.OPTION_VOLUME: ProviderRoute(
            DataCapability.OPTION_VOLUME, "polygon", None
        ),
    }

    @classmethod
    def route(cls, capability: DataCapability) -> ProviderRoute:
        try:
            return cls._ROUTES[capability]
        except KeyError as exc:
            raise ValueError(f"No provider route registered for {capability}") from exc

    @classmethod
    def assert_provider(cls, capability: DataCapability, provider: str) -> None:
        expected = cls.route(capability).primary_provider
        if provider.strip().lower() != expected:
            raise ValueError(
                f"Provider policy violation for {capability.value}: "
                f"expected {expected}, received {provider}"
            )

    @classmethod
    def lineage(cls) -> dict[str, dict[str, str | None]]:
        return {
            capability.value: {
                "primary": route.primary_provider,
                "fallback": route.fallback_provider,
            }
            for capability, route in cls._ROUTES.items()
        }
