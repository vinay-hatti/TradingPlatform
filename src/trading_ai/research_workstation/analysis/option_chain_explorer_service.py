from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from .option_chain_explorer_engine import OptionChainExplorerEngine
from .option_chain_explorer_profile import OptionChainExplorerProfile


class OptionChainExplorerService:
    def __init__(
        self,
        engine: OptionChainExplorerEngine | None = None,
        adapter: Any | None = None,
    ):
        self.engine = engine or OptionChainExplorerEngine()
        self.adapter = adapter

    def analyze_contracts(
        self,
        *,
        symbol: str,
        underlying_price: float,
        contracts: Iterable[Any],
        quote_date: date | None = None,
    ) -> OptionChainExplorerProfile:
        return self.engine.analyze(
            symbol=symbol,
            underlying_price=underlying_price,
            contracts=contracts,
            quote_date=quote_date,
        )

    def analyze_from_repository(
        self,
        *,
        symbol: str,
        underlying_price: float,
        start: date | None = None,
        end: date | None = None,
        quote_date: date | None = None,
    ) -> OptionChainExplorerProfile:
        if self.adapter is None:
            raise ValueError(
                "A repository option-data adapter is required."
            )

        fetch = getattr(self.adapter, "fetch", None)
        if fetch is None:
            fetch = getattr(self.adapter, "load", None)
        if fetch is None:
            fetch = getattr(self.adapter, "get_contracts", None)
        if fetch is None:
            raise TypeError(
                "Option-data adapter must expose fetch(), load(), "
                "or get_contracts()."
            )

        try:
            contracts = fetch(symbol=symbol, start=start, end=end)
        except TypeError:
            contracts = fetch(symbol, start, end)

        return self.analyze_contracts(
            symbol=symbol,
            underlying_price=underlying_price,
            contracts=contracts,
            quote_date=quote_date,
        )
