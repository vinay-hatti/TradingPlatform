from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from statistics import median
from typing import Any, Iterable, Mapping

from .option_chain_explorer_policy import OptionChainExplorerPolicy
from .option_chain_explorer_profile import (
    ExpirationAnalysisProfile,
    OptionChainExplorerProfile,
    OptionContractAnalysisProfile,
)


class OptionChainExplorerEngine:
    def __init__(self, policy: OptionChainExplorerPolicy | None = None):
        self.policy = policy or OptionChainExplorerPolicy()
        self.policy.validate()

    @staticmethod
    def _get(source: Any, *names: str, default: Any = None) -> Any:
        if isinstance(source, Mapping):
            for name in names:
                if name in source:
                    return source[name]
            return default
        for name in names:
            if hasattr(source, name):
                return getattr(source, name)
        return default

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _date(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    @staticmethod
    def _bound(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @staticmethod
    def _ratio(numerator: float, denominator: float) -> float:
        return numerator / denominator if denominator else 0.0

    def _contract(
        self,
        source: Any,
        *,
        symbol: str,
        underlying_price: float,
        quote_date: date,
    ) -> OptionContractAnalysisProfile:
        expiration = self._date(
            self._get(source, "expiration", "expiry", "expiration_date")
        )
        dte = max(0, (expiration - quote_date).days) if expiration else 0
        strike = self._float(self._get(source, "strike"))
        option_type = str(
            self._get(source, "option_type", "contract_type", "type", default="")
        ).upper()
        bid = self._float(self._get(source, "bid"))
        ask = self._float(self._get(source, "ask"))
        last = self._float(self._get(source, "last", "last_price"))
        mark = (bid + ask) / 2.0 if bid > 0 and ask > 0 else last
        spread = max(0.0, ask - bid) if ask > 0 else 0.0
        spread_pct = self._ratio(spread, mark) if mark > 0 else 1.0
        volume = self._int(self._get(source, "volume"))
        open_interest = self._int(
            self._get(source, "open_interest", "openInterest")
        )
        iv = self._float(
            self._get(source, "implied_volatility", "iv")
        )
        delta = self._float(self._get(source, "delta"))
        gamma = self._float(self._get(source, "gamma"))
        theta = self._float(self._get(source, "theta"))
        vega = self._float(self._get(source, "vega"))

        if option_type in {"CALL", "C"}:
            intrinsic = max(0.0, underlying_price - strike)
            normalized_type = "CALL"
        else:
            intrinsic = max(0.0, strike - underlying_price)
            normalized_type = "PUT"
        extrinsic = max(0.0, mark - intrinsic)
        moneyness_pct = (
            ((strike - underlying_price) / underlying_price) * 100.0
            if underlying_price > 0
            else 0.0
        )
        absolute_moneyness = abs(moneyness_pct)
        if absolute_moneyness <= 1.0:
            moneyness = "ATM"
        elif (
            normalized_type == "CALL" and strike < underlying_price
        ) or (
            normalized_type == "PUT" and strike > underlying_price
        ):
            moneyness = "ITM"
        else:
            moneyness = "OTM"

        volume_score = self._bound(
            self._ratio(volume, max(1, self.policy.minimum_volume)) * 50.0
        )
        oi_score = self._bound(
            self._ratio(
                open_interest,
                max(1, self.policy.minimum_open_interest),
            )
            * 50.0
        )
        spread_score = self._bound(
            100.0
            * (
                1.0
                - self._ratio(
                    spread_pct,
                    max(self.policy.maximum_spread_pct, 1e-9),
                )
            )
        )
        moneyness_score = self._bound(100.0 - absolute_moneyness * 10.0)
        greek_score = self._bound(
            100.0 - abs(abs(delta) - 0.50) * 150.0
        )
        liquidity_score = round(
            volume_score * 0.30
            + oi_score * 0.35
            + spread_score * 0.35,
            6,
        )
        contract_score = round(
            volume_score * self.policy.volume_weight
            + oi_score * self.policy.open_interest_weight
            + spread_score * self.policy.spread_weight
            + moneyness_score * self.policy.moneyness_weight
            + greek_score * self.policy.greeks_weight,
            6,
        )

        warnings: list[str] = []
        if volume < self.policy.minimum_volume:
            warnings.append("Option volume below policy minimum")
        if open_interest < self.policy.minimum_open_interest:
            warnings.append("Open interest below policy minimum")
        if spread_pct > self.policy.maximum_spread_pct:
            warnings.append("Bid/ask spread exceeds policy maximum")
        if mark <= 0:
            warnings.append("Contract has no usable market price")

        grade = (
            "A"
            if liquidity_score >= 80
            else "B"
            if liquidity_score >= 65
            else "C"
            if liquidity_score >= 45
            else "D"
        )

        return OptionContractAnalysisProfile(
            symbol=symbol,
            expiration=expiration,
            days_to_expiration=dte,
            strike=strike,
            option_type=normalized_type,
            bid=bid,
            ask=ask,
            mark=round(mark, 6),
            spread=round(spread, 6),
            spread_pct=round(spread_pct, 6),
            volume=volume,
            open_interest=open_interest,
            implied_volatility=iv,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            intrinsic_value=round(intrinsic, 6),
            extrinsic_value=round(extrinsic, 6),
            moneyness_pct=round(moneyness_pct, 6),
            liquidity_score=liquidity_score,
            contract_score=contract_score,
            liquidity_grade=grade,
            moneyness=moneyness,
            warnings=tuple(warnings),
            metadata={"source": "M34_PHASE2_OPTION_CHAIN_EXPLORER"},
        )

    def analyze(
        self,
        *,
        symbol: str,
        underlying_price: float,
        contracts: Iterable[Any],
        quote_date: date | None = None,
    ) -> OptionChainExplorerProfile:
        effective_quote_date = quote_date or date.today()
        normalized = tuple(
            self._contract(
                contract,
                symbol=symbol,
                underlying_price=underlying_price,
                quote_date=effective_quote_date,
            )
            for contract in contracts
        )

        groups: dict[date | None, list[OptionContractAnalysisProfile]] = (
            defaultdict(list)
        )
        for contract in normalized:
            groups[contract.expiration].append(contract)

        expiration_profiles: list[ExpirationAnalysisProfile] = []
        for expiration, items in groups.items():
            calls = [item for item in items if item.option_type == "CALL"]
            puts = [item for item in items if item.option_type == "PUT"]
            total_volume = sum(item.volume for item in items)
            total_oi = sum(item.open_interest for item in items)
            avg_spread = (
                sum(item.spread_pct for item in items) / len(items)
                if items
                else 0.0
            )
            median_iv = median(
                [item.implied_volatility for item in items]
            ) if items else 0.0
            liquidity = (
                sum(item.liquidity_score for item in items) / len(items)
                if items
                else 0.0
            )
            dte = items[0].days_to_expiration if items else 0
            dte_quality = (
                100.0
                if self.policy.preferred_minimum_dte
                <= dte
                <= self.policy.preferred_maximum_dte
                else max(
                    0.0,
                    100.0
                    - min(
                        abs(dte - self.policy.preferred_minimum_dte),
                        abs(dte - self.policy.preferred_maximum_dte),
                    )
                    * 4.0,
                )
            )
            expiration_score = round(
                liquidity * 0.75 + dte_quality * 0.25,
                6,
            )
            warnings: list[str] = []
            if avg_spread > self.policy.maximum_spread_pct:
                warnings.append("Average spread exceeds policy maximum")
            if total_volume == 0:
                warnings.append("Expiration has no reported option volume")
            if total_oi == 0:
                warnings.append("Expiration has no reported open interest")

            grade = (
                "A"
                if expiration_score >= 80
                else "B"
                if expiration_score >= 65
                else "C"
                if expiration_score >= 45
                else "D"
            )
            expiration_profiles.append(
                ExpirationAnalysisProfile(
                    expiration=expiration,
                    days_to_expiration=dte,
                    contract_count=len(items),
                    call_count=len(calls),
                    put_count=len(puts),
                    total_volume=total_volume,
                    total_open_interest=total_oi,
                    average_spread_pct=round(avg_spread, 6),
                    median_implied_volatility=round(median_iv, 6),
                    call_put_volume_ratio=round(
                        self._ratio(
                            sum(item.volume for item in calls),
                            sum(item.volume for item in puts),
                        ),
                        6,
                    ),
                    call_put_open_interest_ratio=round(
                        self._ratio(
                            sum(item.open_interest for item in calls),
                            sum(item.open_interest for item in puts),
                        ),
                        6,
                    ),
                    liquidity_score=round(liquidity, 6),
                    expiration_score=expiration_score,
                    quality_grade=grade,
                    preferred=False,
                    warnings=tuple(warnings),
                )
            )

        expiration_profiles.sort(
            key=lambda item: (
                -item.expiration_score,
                item.days_to_expiration,
            )
        )
        preferred_expiration = (
            expiration_profiles[0].expiration
            if expiration_profiles
            else None
        )
        expiration_profiles = [
            ExpirationAnalysisProfile(
                **{
                    **profile.__dict__,
                    "preferred": profile.expiration == preferred_expiration,
                }
            )
            for profile in expiration_profiles
        ]

        ranked_contracts = tuple(
            sorted(
                (
                    item
                    for item in normalized
                    if item.contract_score
                    >= self.policy.minimum_contract_score
                ),
                key=lambda item: (
                    item.expiration or date.max,
                    -item.contract_score,
                    item.strike,
                ),
            )
        )

        warnings: list[str] = []
        if not normalized:
            warnings.append("No option contracts were supplied")
        if normalized and not expiration_profiles:
            warnings.append("No valid expirations were detected")

        return OptionChainExplorerProfile(
            symbol=symbol,
            underlying_price=float(underlying_price),
            quote_date=effective_quote_date,
            contract_count=len(normalized),
            expiration_count=len(expiration_profiles),
            preferred_expiration=preferred_expiration,
            expirations=tuple(expiration_profiles),
            contracts=ranked_contracts,
            warnings=tuple(warnings),
            metadata={
                "source": "M34_PHASE2_OPTION_CHAIN_EXPLORER",
                "policy_version": "1.0",
            },
        )
