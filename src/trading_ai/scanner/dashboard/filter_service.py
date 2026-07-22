from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Iterable


from .filter_contracts import ScannerFilter


class ScannerFilterService:
    _ALIASES: dict[str, tuple[str, ...]] = {
        "institutional_score": (
            "institutional_score",
            "score",
            "ranking_score",
            "composite_score",
        ),
        "probability_of_profit": (
            "probability_of_profit",
            "probability",
            "pop",
            "win_probability",
            "calibrated_probability",
        ),
        "liquidity_score": (
            "liquidity_score",
            "option_liquidity_score",
            "market_liquidity_score",
        ),
        "open_interest": (
            "open_interest",
            "option_open_interest",
            "total_open_interest",
        ),
        "volume": (
            "volume",
            "option_volume",
            "total_volume",
        ),
        "spread_pct": (
            "spread_pct",
            "bid_ask_spread_pct",
            "max_spread_pct",
        ),
        "sector": ("sector", "gics_sector", "industry_sector"),
        "direction": (
            "direction",
            "signal",
            "bias",
            "trade_direction",
            "option_type",
        ),
        "strategy_type": (
            "strategy_type",
            "strategy",
            "recommended_strategy",
            "structure",
        ),
        "symbol": ("symbol", "ticker", "underlying_symbol"),
    }

    def apply(
        self,
        records: Iterable[Any],
        filters: ScannerFilter,
    ) -> list[Any]:
        return [
            record
            for record in records
            if self._matches(record, filters)
        ]

    def _matches(self, record: Any, filters: ScannerFilter) -> bool:
        institutional_score = self._number(
            record, "institutional_score"
        )
        if (
            filters.min_institutional_score is not None
            and (
                institutional_score is None
                or institutional_score < filters.min_institutional_score
            )
        ):
            return False
        if (
            filters.max_institutional_score is not None
            and (
                institutional_score is None
                or institutional_score > filters.max_institutional_score
            )
        ):
            return False

        probability = self._number(record, "probability_of_profit")
        if (
            filters.min_probability_of_profit is not None
            and (
                probability is None
                or probability < filters.min_probability_of_profit
            )
        ):
            return False
        if (
            filters.max_probability_of_profit is not None
            and (
                probability is None
                or probability > filters.max_probability_of_profit
            )
        ):
            return False

        liquidity = self._number(record, "liquidity_score")
        if (
            filters.min_liquidity_score is not None
            and (
                liquidity is None
                or liquidity < filters.min_liquidity_score
            )
        ):
            return False

        open_interest = self._number(record, "open_interest")
        if (
            filters.min_open_interest is not None
            and (
                open_interest is None
                or open_interest < filters.min_open_interest
            )
        ):
            return False

        volume = self._number(record, "volume")
        if (
            filters.min_volume is not None
            and (volume is None or volume < filters.min_volume)
        ):
            return False

        spread_pct = self._number(record, "spread_pct")
        if (
            filters.max_spread_pct is not None
            and (
                spread_pct is None
                or spread_pct > filters.max_spread_pct
            )
        ):
            return False

        if not self._matches_allowed(
            record, "sector", filters.sectors
        ):
            return False
        if not self._matches_allowed(
            record, "direction", filters.directions
        ):
            return False
        if not self._matches_allowed(
            record, "strategy_type", filters.strategy_types
        ):
            return False
        if not self._matches_allowed(
            record, "symbol", filters.symbols
        ):
            return False

        symbol = self._text(record, "symbol")
        excluded = {value.upper() for value in filters.exclude_symbols}
        if symbol and symbol.upper() in excluded:
            return False

        return True

    def _matches_allowed(
        self,
        record: Any,
        field_name: str,
        allowed: tuple[str, ...],
    ) -> bool:
        if not allowed:
            return True
        value = self._text(record, field_name)
        if value is None:
            return False
        normalized_allowed = {item.upper() for item in allowed}
        return value.upper() in normalized_allowed

    def _payload(self, record: Any) -> Any:
        if record is None:
            return None
        if isinstance(record, (dict, list, tuple)):
            return record
        if is_dataclass(record):
            return asdict(record)
        if hasattr(record, "model_dump"):
            try:
                return record.model_dump()
            except TypeError:
                pass
        if hasattr(record, "dict"):
            try:
                return record.dict()
            except TypeError:
                pass
        if hasattr(record, "__dict__"):
            return {
                key: value
                for key, value in vars(record).items()
                if not key.startswith("_")
            }
        return record

    def _recursive_find(
        self,
        value: Any,
        aliases: tuple[str, ...],
        *,
        visited: set[int] | None = None,
        depth: int = 0,
    ) -> Any:
        if value is None or depth > 8:
            return None

        if visited is None:
            visited = set()

        if not isinstance(value, (str, bytes, int, float, bool)):
            object_id = id(value)
            if object_id in visited:
                return None
            visited.add(object_id)

        payload = self._payload(value)

        if isinstance(payload, dict):
            for alias in aliases:
                if alias in payload and payload[alias] is not None:
                    return payload[alias]

            preferred_wrappers = (
                "raw",
                "raw_record",
                "record",
                "source",
                "source_record",
                "payload",
                "data",
                "attributes",
                "fields",
                "metrics",
                "scores",
                "ranking",
                "candidate",
                "opportunity",
                "market_data",
                "option_metrics",
            )
            for key in preferred_wrappers:
                if key in payload:
                    result = self._recursive_find(
                        payload[key],
                        aliases,
                        visited=visited,
                        depth=depth + 1,
                    )
                    if result is not None:
                        return result

            for child in payload.values():
                result = self._recursive_find(
                    child,
                    aliases,
                    visited=visited,
                    depth=depth + 1,
                )
                if result is not None:
                    return result
            return None

        if isinstance(payload, (list, tuple)):
            for child in payload:
                result = self._recursive_find(
                    child,
                    aliases,
                    visited=visited,
                    depth=depth + 1,
                )
                if result is not None:
                    return result
            return None

        for alias in aliases:
            try:
                result = getattr(value, alias)
            except (AttributeError, TypeError):
                continue
            if result is not None:
                return result

        return None

    def _value(self, record: Any, field_name: str) -> Any:
        return self._recursive_find(record, self._ALIASES[field_name])

    def _number(self, record: Any, field_name: str) -> float | None:
        value = self._value(record, field_name)
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = value.strip().rstrip("%")
            number = float(value)
            if (
                field_name in ("probability_of_profit", "spread_pct")
                and number > 1.0
            ):
                number /= 100.0
            return number
        except (TypeError, ValueError):
            return None

    def _text(self, record: Any, field_name: str) -> str | None:
        value = self._value(record, field_name)
        if value is None:
            return None
        return str(value).strip()
