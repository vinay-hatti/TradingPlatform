from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Sequence

from .options_data_adapter import OptionContractSnapshot
from .options_enrichment_profile import OptionLiquiditySnapshot


class OptionsEnrichmentEngine:
    def __init__(
        self,
        *,
        minimum_contract_volume: int = 1,
        minimum_contract_open_interest: int = 1,
        maximum_contract_spread_pct: float = 1.0,
    ):
        self.minimum_contract_volume = minimum_contract_volume
        self.minimum_contract_open_interest = minimum_contract_open_interest
        self.maximum_contract_spread_pct = maximum_contract_spread_pct

    @staticmethod
    def _spread_pct(contract: OptionContractSnapshot) -> float:
        midpoint = (contract.bid + contract.ask) / 2.0
        if midpoint <= 0:
            return 1.0
        return max(0.0, (contract.ask - contract.bid) / midpoint)

    @staticmethod
    def _percentile_rank(values: Sequence[float], current: float) -> float:
        clean = sorted(value for value in values if value > 0)
        if not clean:
            return 0.0
        less_or_equal = sum(1 for value in clean if value <= current)
        return round((less_or_equal / len(clean)) * 100.0, 6)

    @staticmethod
    def _iv_rank(values: Sequence[float], current: float) -> float:
        clean = [value for value in values if value > 0]
        if not clean:
            return 0.0
        minimum = min(clean)
        maximum = max(clean)
        if maximum == minimum:
            return 50.0
        return round(((current - minimum) / (maximum - minimum)) * 100.0, 6)

    def build_snapshot(
        self,
        symbol: str,
        contracts: Sequence[OptionContractSnapshot],
    ) -> OptionLiquiditySnapshot | None:
        if not contracts:
            return None

        by_quote_date: dict = defaultdict(list)
        for contract in contracts:
            by_quote_date[contract.quote_date].append(contract)

        latest_date = max(by_quote_date)
        latest_contracts = by_quote_date[latest_date]

        spreads = [self._spread_pct(contract) for contract in latest_contracts]
        implied_volatilities = [
            contract.implied_volatility
            for contract in latest_contracts
            if contract.implied_volatility > 0
        ]

        history_medians: list[float] = []
        for quote_date in sorted(by_quote_date):
            day_ivs = [
                contract.implied_volatility
                for contract in by_quote_date[quote_date]
                if contract.implied_volatility > 0
            ]
            if day_ivs:
                history_medians.append(median(day_ivs))

        current_iv = median(implied_volatilities) if implied_volatilities else 0.0

        liquid_contracts = [
            contract
            for contract in latest_contracts
            if contract.volume >= self.minimum_contract_volume
            and contract.open_interest >= self.minimum_contract_open_interest
            and self._spread_pct(contract) <= self.maximum_contract_spread_pct
        ]

        return OptionLiquiditySnapshot(
            symbol=symbol,
            quote_date=latest_date,
            option_volume=sum(contract.volume for contract in latest_contracts),
            open_interest=sum(contract.open_interest for contract in latest_contracts),
            median_spread_pct=round(median(spreads) if spreads else 1.0, 6),
            iv_rank=self._iv_rank(history_medians, current_iv),
            iv_percentile=self._percentile_rank(history_medians, current_iv),
            contract_count=len(latest_contracts),
            liquid_contract_count=len(liquid_contracts),
        )
