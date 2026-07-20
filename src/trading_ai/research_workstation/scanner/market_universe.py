from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True)
class MarketUniverseProfile:
    name: str
    symbols: tuple[str, ...]
    description: str = ""

    def normalized_symbols(self) -> tuple[str, ...]:
        seen: set[str] = set()
        normalized: list[str] = []
        for symbol in self.symbols:
            value = symbol.strip().upper()
            if value and value not in seen:
                seen.add(value)
                normalized.append(value)
        return tuple(normalized)


class MarketUniverseProvider(Protocol):
    def load(self, name: str) -> MarketUniverseProfile:
        ...


class StaticMarketUniverseProvider:
    def __init__(self, universes: Iterable[MarketUniverseProfile] | None = None):
        defaults = universes or (
            MarketUniverseProfile(
                name="core_mega_cap",
                symbols=("AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "TSLA"),
                description="Core liquid mega-cap equity universe.",
            ),
            MarketUniverseProfile(
                name="core_options",
                symbols=("AAPL", "MSFT", "AMZN", "NVDA", "AMD", "META", "TSLA", "SPY", "QQQ"),
                description="Highly liquid names suitable for options research.",
            ),
        )
        self._universes = {
            universe.name: MarketUniverseProfile(
                name=universe.name,
                symbols=universe.normalized_symbols(),
                description=universe.description,
            )
            for universe in defaults
        }

    def load(self, name: str) -> MarketUniverseProfile:
        try:
            return self._universes[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._universes))
            raise KeyError(
                f"Unknown market universe '{name}'. Available: {available}"
            ) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._universes))
