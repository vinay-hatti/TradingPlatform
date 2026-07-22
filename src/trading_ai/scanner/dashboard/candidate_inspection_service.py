from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Iterable

from .candidate_inspection_profile import CandidateInspectionProfile


class CandidateInspectionService:
    _ALIASES: dict[str, tuple[str, ...]] = {
        "symbol": ("symbol", "ticker", "underlying_symbol"),
        "rank": ("rank", "ranking", "position"),
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
        "sector": ("sector", "gics_sector", "industry_sector"),
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
        "volume": ("volume", "option_volume", "total_volume"),
        "spread_pct": (
            "spread_pct",
            "bid_ask_spread_pct",
            "max_spread_pct",
        ),
        "underlying_price": (
            "underlying_price",
            "spot_price",
            "price",
            "close",
        ),
        "expected_move": (
            "expected_move",
            "expected_move_pct",
            "expected_move_1d",
        ),
        "market_regime": (
            "market_regime",
            "regime",
            "current_regime",
        ),
        "warnings": ("warnings", "warning_messages"),
        "rejections": ("rejections", "rejection_reasons"),
    }

    def inspect(
        self,
        records: Iterable[Any],
        symbol: str,
    ) -> CandidateInspectionProfile:
        requested = symbol.strip().upper()
        if not requested:
            raise ValueError("Candidate symbol cannot be empty.")

        match = None
        for record in records:
            record_symbol = self._text(record, "symbol")
            if record_symbol and record_symbol.upper() == requested:
                match = record
                break

        if match is None:
            available = sorted(
                {
                    value.upper()
                    for record in records
                    if (value := self._text(record, "symbol"))
                }
            )
            raise KeyError(
                f"Candidate not found: {requested}. "
                f"Available symbols: {available}"
            )

        return CandidateInspectionProfile(
            symbol=requested,
            rank=self._integer(match, "rank"),
            institutional_score=self._number(
                match, "institutional_score"
            ),
            probability_of_profit=self._ratio(
                match, "probability_of_profit"
            ),
            direction=self._text(match, "direction"),
            strategy_type=self._text(match, "strategy_type"),
            sector=self._text(match, "sector"),
            liquidity_score=self._number(match, "liquidity_score"),
            open_interest=self._integer(match, "open_interest"),
            volume=self._integer(match, "volume"),
            spread_pct=self._ratio(match, "spread_pct"),
            underlying_price=self._number(match, "underlying_price"),
            expected_move=self._number(match, "expected_move"),
            market_regime=self._text(match, "market_regime"),
            warnings=self._text_tuple(match, "warnings"),
            rejections=self._text_tuple(match, "rejections"),
            metadata={"source_record": self._payload(match)},
            option_chain_command=(
                "uv",
                "run",
                "python",
                "-m",
                "trading_ai",
                "option-chain",
                "--symbol",
                requested,
            ),
            strategy_comparison_command=(
                "uv",
                "run",
                "python",
                "-m",
                "trading_ai",
                "compare-strategies",
                "--symbol",
                requested,
            ),
            institutional_decision_command=(
                "uv",
                "run",
                "python",
                "-m",
                "trading_ai",
                "institutional-decision",
                "--symbol",
                requested,
            ),
        )

    def _payload(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list, tuple, str, int, float, bool)):
            return value
        if is_dataclass(value):
            return asdict(value)
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump()
            except TypeError:
                pass
        if hasattr(value, "dict"):
            try:
                return value.dict()
            except TypeError:
                pass
        if hasattr(value, "__dict__"):
            return {
                key: child
                for key, child in vars(value).items()
                if not key.startswith("_")
            }
        return value

    def _find(
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
            for child in payload.values():
                found = self._find(
                    child,
                    aliases,
                    visited=visited,
                    depth=depth + 1,
                )
                if found is not None:
                    return found
            return None

        if isinstance(payload, (list, tuple)):
            for child in payload:
                found = self._find(
                    child,
                    aliases,
                    visited=visited,
                    depth=depth + 1,
                )
                if found is not None:
                    return found
            return None

        for alias in aliases:
            try:
                found = getattr(value, alias)
            except (AttributeError, TypeError):
                continue
            if found is not None:
                return found
        return None

    def _value(self, record: Any, field_name: str) -> Any:
        return self._find(record, self._ALIASES[field_name])

    def _text(self, record: Any, field_name: str) -> str | None:
        value = self._value(record, field_name)
        if value is None:
            return None
        return str(value).strip()

    def _number(self, record: Any, field_name: str) -> float | None:
        value = self._value(record, field_name)
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = value.strip().rstrip("%")
            return float(value)
        except (TypeError, ValueError):
            return None

    def _ratio(self, record: Any, field_name: str) -> float | None:
        value = self._number(record, field_name)
        if value is None:
            return None
        return value / 100.0 if value > 1.0 else value

    def _integer(self, record: Any, field_name: str) -> int | None:
        value = self._number(record, field_name)
        return int(value) if value is not None else None

    def _text_tuple(
        self,
        record: Any,
        field_name: str,
    ) -> tuple[str, ...]:
        value = self._value(record, field_name)
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,)
        if isinstance(value, (list, tuple, set)):
            return tuple(str(item) for item in value)
        return (str(value),)
