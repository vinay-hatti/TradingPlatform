from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .contracts import OptionContractIdentity, OptionQuoteRecord, OptionSide


class OptionQuoteNormalizer:
    CALL_ALIASES = {"C", "CALL", "CALLS", "CE"}
    PUT_ALIASES = {"P", "PUT", "PUTS", "PE"}

    FIELD_ALIASES = {
        "underlying_symbol": (
            "underlying_symbol",
            "underlying",
            "symbol",
            "ticker",
        ),
        "expiration_date": (
            "expiration_date",
            "expiration",
            "expiry",
            "expiry_date",
        ),
        "quote_date": (
            "quote_date",
            "date",
            "trade_date",
            "as_of_date",
        ),
        "strike": ("strike", "strike_price"),
        "option_side": (
            "option_side",
            "option_type",
            "type",
            "right",
            "put_call",
        ),
        "bid": ("bid", "bid_price"),
        "ask": ("ask", "ask_price"),
        "last": ("last", "last_price", "mark"),
        "volume": ("volume", "vol"),
        "open_interest": ("open_interest", "openinterest", "oi"),
        "implied_volatility": (
            "implied_volatility",
            "impliedvolatility",
            "iv",
        ),
        "delta": ("delta",),
        "gamma": ("gamma",),
        "theta": ("theta",),
        "vega": ("vega",),
        "provider_symbol": (
            "provider_symbol",
            "contract_symbol",
            "option_symbol",
        ),
    }

    def normalize(self, raw: Mapping[str, Any]) -> OptionQuoteRecord:
        normalized_raw = {
            self._normalize_field_name(key): value
            for key, value in raw.items()
        }

        underlying = self._required_text(
            self._find(normalized_raw, "underlying_symbol"),
            "underlying_symbol",
        ).upper()
        expiration = self._parse_date(
            self._find(normalized_raw, "expiration_date"),
            "expiration_date",
        )
        quote_date = self._parse_date(
            self._find(normalized_raw, "quote_date"),
            "quote_date",
        )
        strike = self._required_float(
            self._find(normalized_raw, "strike"),
            "strike",
        )
        side = self._parse_side(
            self._find(normalized_raw, "option_side")
        )

        identity = OptionContractIdentity(
            underlying_symbol=underlying,
            expiration_date=expiration,
            strike=strike,
            option_side=side,
        )

        recognized_keys = {
            alias
            for aliases in self.FIELD_ALIASES.values()
            for alias in aliases
        }
        metadata = {
            key: value
            for key, value in normalized_raw.items()
            if key not in recognized_keys
        }

        return OptionQuoteRecord(
            identity=identity,
            quote_date=quote_date,
            bid=self._optional_float(self._find(normalized_raw, "bid")),
            ask=self._optional_float(self._find(normalized_raw, "ask")),
            last=self._optional_float(self._find(normalized_raw, "last")),
            volume=self._optional_int(self._find(normalized_raw, "volume")),
            open_interest=self._optional_int(
                self._find(normalized_raw, "open_interest")
            ),
            implied_volatility=self._optional_float(
                self._find(normalized_raw, "implied_volatility")
            ),
            delta=self._optional_float(self._find(normalized_raw, "delta")),
            gamma=self._optional_float(self._find(normalized_raw, "gamma")),
            theta=self._optional_float(self._find(normalized_raw, "theta")),
            vega=self._optional_float(self._find(normalized_raw, "vega")),
            provider_symbol=self._optional_text(
                self._find(normalized_raw, "provider_symbol")
            ),
            metadata=metadata,
        )

    def _find(self, raw: Mapping[str, Any], canonical: str) -> Any:
        for alias in self.FIELD_ALIASES[canonical]:
            if alias in raw:
                return raw[alias]
        return None

    @staticmethod
    def _normalize_field_name(value: object) -> str:
        return (
            str(value)
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

    @classmethod
    def _parse_side(cls, value: Any) -> OptionSide:
        normalized = cls._required_text(value, "option_side").upper()
        if normalized in cls.CALL_ALIASES:
            return OptionSide.CALL
        if normalized in cls.PUT_ALIASES:
            return OptionSide.PUT
        raise ValueError(f"Unsupported option side: {value!r}")

    @staticmethod
    def _parse_date(value: Any, field_name: str) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if value is None or str(value).strip() == "":
            raise ValueError(f"{field_name} is required")

        text = str(value).strip()
        formats = (
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%Y%m%d",
            "%m-%d-%Y",
        )
        for date_format in formats:
            try:
                return datetime.strptime(text, date_format).date()
            except ValueError:
                continue
        raise ValueError(
            f"{field_name} has unsupported date format: {value!r}"
        )

    @staticmethod
    def _required_text(value: Any, field_name: str) -> str:
        if value is None:
            raise ValueError(f"{field_name} is required")
        normalized = str(value).strip()
        if not normalized:
            raise ValueError(f"{field_name} is required")
        return normalized

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @classmethod
    def _required_float(cls, value: Any, field_name: str) -> float:
        result = cls._optional_float(value)
        if result is None:
            raise ValueError(f"{field_name} is required")
        return result

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            return float(Decimal(str(value).replace(",", "").strip()))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Invalid numeric value: {value!r}") from exc

    @classmethod
    def _optional_int(cls, value: Any) -> int | None:
        numeric = cls._optional_float(value)
        if numeric is None:
            return None
        if not numeric.is_integer():
            raise ValueError(f"Expected integral value: {value!r}")
        return int(numeric)
