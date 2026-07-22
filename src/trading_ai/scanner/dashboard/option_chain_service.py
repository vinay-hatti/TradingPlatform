from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Iterable

from .option_chain_profile import (
    OptionChainInspectionProfile,
    OptionContractInspection,
)


class OptionChainInspectionService:
    STRICT = "STRICT"
    HISTORICAL_ALLOW_MISSING_QUOTES = "HISTORICAL_ALLOW_MISSING_QUOTES"

    def inspect(
        self,
        records: Iterable[Any],
        symbol: str,
        *,
        min_volume: int = 0,
        min_open_interest: int = 0,
        max_spread_pct: float = 1.0,
        expiry: str | None = None,
        option_type: str | None = None,
        quote_policy: str = STRICT,
    ) -> OptionChainInspectionProfile:
        requested = symbol.strip().upper()
        normalized_type = option_type.upper() if option_type else None
        policy = quote_policy.strip().upper()
        if policy not in {
            self.STRICT,
            self.HISTORICAL_ALLOW_MISSING_QUOTES,
        }:
            raise ValueError(f"Unsupported quote policy: {quote_policy}")

        contracts: list[OptionContractInspection] = []
        total = 0
        quote_date: str | None = None
        underlying_price: float | None = None

        rejection_counts = {
            "expiry_mismatch": 0,
            "option_type_mismatch": 0,
            "missing_volume": 0,
            "volume_below_minimum": 0,
            "missing_open_interest": 0,
            "open_interest_below_minimum": 0,
            "missing_or_invalid_bid_ask": 0,
            "spread_above_maximum": 0,
        }
        field_coverage = {
            "volume_present": 0,
            "open_interest_present": 0,
            "bid_present": 0,
            "ask_present": 0,
            "valid_spread": 0,
        }
        observed_values: dict[str, list[float]] = {
            "volume": [],
            "open_interest": [],
            "spread_pct": [],
            "bid": [],
            "ask": [],
        }

        for raw in records:
            payload = self._payload(raw)
            contract_symbol = self._text(
                payload,
                ("underlying_symbol", "symbol", "ticker"),
            )
            if not contract_symbol or contract_symbol.upper() != requested:
                continue

            total += 1
            contract_expiry = self._text(
                payload, ("expiry", "expiration", "expiration_date")
            )
            contract_type = self._text(
                payload, ("option_type", "type", "right")
            )
            if contract_type:
                contract_type = self._normalize_option_type(contract_type)

            volume = self._integer(payload, ("volume",))
            open_interest = self._integer(
                payload, ("open_interest", "oi")
            )
            bid = self._number(payload, ("bid",))
            ask = self._number(payload, ("ask",))
            spread_pct = self._spread_pct(bid, ask)

            if volume is not None:
                field_coverage["volume_present"] += 1
                observed_values["volume"].append(float(volume))
            if open_interest is not None:
                field_coverage["open_interest_present"] += 1
                observed_values["open_interest"].append(float(open_interest))
            if bid is not None:
                field_coverage["bid_present"] += 1
                observed_values["bid"].append(bid)
            if ask is not None:
                field_coverage["ask_present"] += 1
                observed_values["ask"].append(ask)
            if spread_pct is not None:
                field_coverage["valid_spread"] += 1
                observed_values["spread_pct"].append(spread_pct)

            if expiry and contract_expiry != expiry:
                rejection_counts["expiry_mismatch"] += 1
                continue
            if normalized_type and contract_type != normalized_type:
                rejection_counts["option_type_mismatch"] += 1
                continue
            if volume is None:
                rejection_counts["missing_volume"] += 1
                continue
            if volume < min_volume:
                rejection_counts["volume_below_minimum"] += 1
                continue
            if open_interest is None:
                rejection_counts["missing_open_interest"] += 1
                continue
            if open_interest < min_open_interest:
                rejection_counts["open_interest_below_minimum"] += 1
                continue

            warnings: list[str] = []
            if spread_pct is None:
                if policy == self.STRICT:
                    rejection_counts["missing_or_invalid_bid_ask"] += 1
                    continue
                warnings.append("HISTORICAL_QUOTES_UNAVAILABLE")
            elif spread_pct > max_spread_pct:
                rejection_counts["spread_above_maximum"] += 1
                continue

            if spread_pct is not None and spread_pct > 0.20:
                warnings.append("WIDE_SPREAD")
            if volume == 0:
                warnings.append("ZERO_VOLUME")
            if open_interest == 0:
                warnings.append("ZERO_OPEN_INTEREST")

            mid_price = (
                (bid + ask) / 2.0
                if bid is not None and ask is not None
                else None
            )
            liquidity_status = (
                "HISTORICAL_NO_QUOTE"
                if spread_pct is None
                else self._liquidity_status(
                    volume,
                    open_interest,
                    spread_pct,
                )
            )

            contracts.append(
                OptionContractInspection(
                    symbol=requested,
                    expiry=contract_expiry or "",
                    strike=self._number(payload, ("strike",)) or 0.0,
                    option_type=contract_type or "UNKNOWN",
                    bid=bid,
                    ask=ask,
                    last=self._number(payload, ("last", "last_price")),
                    volume=volume,
                    open_interest=open_interest,
                    implied_volatility=self._ratio(
                        payload,
                        ("implied_volatility", "iv"),
                    ),
                    delta=self._number(payload, ("delta",)),
                    gamma=self._number(payload, ("gamma",)),
                    theta=self._number(payload, ("theta",)),
                    vega=self._number(payload, ("vega",)),
                    spread_pct=spread_pct,
                    mid_price=mid_price,
                    liquidity_status=liquidity_status,
                    warnings=tuple(warnings),
                    metadata={"source_record": payload},
                )
            )

            quote_date = quote_date or self._text(
                payload, ("quote_date", "date", "as_of")
            )
            underlying_price = underlying_price or self._number(
                payload,
                ("underlying_price", "spot_price", "underlying_last"),
            )

        contracts.sort(
            key=lambda item: (item.expiry, item.option_type, item.strike)
        )
        calls = tuple(
            item for item in contracts if item.option_type == "CALL"
        )
        puts = tuple(
            item for item in contracts if item.option_type == "PUT"
        )

        warnings: list[str] = []
        if total == 0:
            warnings.append("NO_CONTRACTS_FOR_SYMBOL")
        elif not contracts:
            warnings.append("NO_CONTRACTS_PASSED_FILTERS")
        if (
            policy == self.HISTORICAL_ALLOW_MISSING_QUOTES
            and field_coverage["valid_spread"] == 0
        ):
            warnings.append("HISTORICAL_DATA_WITHOUT_BID_ASK_QUOTES")

        return OptionChainInspectionProfile(
            symbol=requested,
            quote_date=quote_date,
            underlying_price=underlying_price,
            total_contracts=total,
            filtered_contracts=len(contracts),
            expiries=tuple(sorted({item.expiry for item in contracts})),
            calls=calls,
            puts=puts,
            warnings=tuple(warnings),
            rejection_counts=rejection_counts,
            field_coverage=field_coverage,
            observed_ranges={
                name: self._range(values)
                for name, values in observed_values.items()
            },
            quote_policy=policy,
        )

    def _range(self, values: list[float]) -> dict[str, float | int | None]:
        if not values:
            return {"count": 0, "min": None, "max": None}
        return {"count": len(values), "min": min(values), "max": max(values)}

    def _payload(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        if hasattr(value, "__dict__"):
            return {
                key: child
                for key, child in vars(value).items()
                if not key.startswith("_")
            }
        return {}

    def _value(
        self,
        payload: dict[str, Any],
        aliases: tuple[str, ...],
    ) -> Any:
        for alias in aliases:
            value = payload.get(alias)
            if value not in (None, ""):
                return value
        for wrapper in (
            "contract",
            "option",
            "greeks",
            "market_data",
            "quote",
            "metadata",
        ):
            nested = payload.get(wrapper)
            if isinstance(nested, dict):
                for alias in aliases:
                    value = nested.get(alias)
                    if value not in (None, ""):
                        return value
        return None

    def _text(
        self,
        payload: dict[str, Any],
        aliases: tuple[str, ...],
    ) -> str | None:
        value = self._value(payload, aliases)
        return None if value is None else str(value).strip()

    def _number(
        self,
        payload: dict[str, Any],
        aliases: tuple[str, ...],
    ) -> float | None:
        value = self._value(payload, aliases)
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = value.strip().rstrip("%")
            return float(value)
        except (TypeError, ValueError):
            return None

    def _integer(
        self,
        payload: dict[str, Any],
        aliases: tuple[str, ...],
    ) -> int | None:
        value = self._number(payload, aliases)
        return int(value) if value is not None else None

    def _ratio(
        self,
        payload: dict[str, Any],
        aliases: tuple[str, ...],
    ) -> float | None:
        value = self._number(payload, aliases)
        if value is None:
            return None
        return value / 100.0 if value > 1.0 else value

    def _normalize_option_type(self, value: str) -> str:
        normalized = value.strip().upper()
        if normalized in {"C", "CALL"}:
            return "CALL"
        if normalized in {"P", "PUT"}:
            return "PUT"
        return normalized

    def _spread_pct(
        self,
        bid: float | None,
        ask: float | None,
    ) -> float | None:
        if bid is None or ask is None or ask < bid:
            return None
        mid = (bid + ask) / 2.0
        if mid <= 0:
            return None
        return (ask - bid) / mid

    def _liquidity_status(
        self,
        volume: int | None,
        open_interest: int | None,
        spread_pct: float | None,
    ) -> str:
        if (
            volume is None
            or open_interest is None
            or spread_pct is None
        ):
            return "UNKNOWN"
        if volume >= 500 and open_interest >= 1000 and spread_pct <= 0.10:
            return "HIGH"
        if volume >= 100 and open_interest >= 500 and spread_pct <= 0.20:
            return "MEDIUM"
        return "LOW"
