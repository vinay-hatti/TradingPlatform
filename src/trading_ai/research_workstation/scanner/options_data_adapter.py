from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Protocol

from trading_ai.database import SessionLocal
from trading_ai.database.repositories.option_chain import OptionChainRepository


@dataclass(frozen=True)
class OptionContractSnapshot:
    underlying_symbol: str
    expiry: date
    quote_date: date
    strike: float
    option_type: str
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None


class OptionsDataAdapter(Protocol):
    def load_contracts(
        self,
        *,
        symbols: Iterable[str],
        start: date | None = None,
        end: date | None = None,
    ) -> dict[str, tuple[OptionContractSnapshot, ...]]:
        ...


class RepositoryOptionsDataAdapter:
    def __init__(self, session_factory=SessionLocal, table_name: str | None = None):
        self._session_factory = session_factory
        self._table_name = table_name
        self.last_resolved_table_name: str | None = None

    @staticmethod
    def _date(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        return default if value is None else float(value)

    @staticmethod
    def _int(value: Any, default: int = 0) -> int:
        return default if value is None else int(float(value))

    def load_contracts(
        self,
        *,
        symbols: Iterable[str],
        start: date | None = None,
        end: date | None = None,
    ) -> dict[str, tuple[OptionContractSnapshot, ...]]:
        normalized = tuple(
            dict.fromkeys(s.strip().upper() for s in symbols if s and s.strip())
        )
        grouped: dict[str, list[OptionContractSnapshot]] = {
            symbol: [] for symbol in normalized
        }
        with self._session_factory() as session:
            repository = OptionChainRepository(session, table_name=self._table_name)
            rows = repository.get_range(normalized, start=start, end=end)
            self.last_resolved_table_name = repository.resolved_table_name

        for row in rows:
            symbol = str(row["symbol"]).upper()
            grouped.setdefault(symbol, []).append(
                OptionContractSnapshot(
                    underlying_symbol=symbol,
                    expiry=self._date(row["expiry"]),
                    quote_date=self._date(row["quote_date"]),
                    strike=self._float(row["strike"]),
                    option_type=str(row["option_type"]).lower(),
                    bid=self._float(row["bid"]),
                    ask=self._float(row["ask"]),
                    last=self._float(row.get("last")),
                    volume=self._int(row["volume"]),
                    open_interest=self._int(row["open_interest"]),
                    implied_volatility=self._float(row["implied_volatility"]),
                    delta=self._float(row.get("delta")) if row.get("delta") is not None else None,
                    gamma=self._float(row.get("gamma")) if row.get("gamma") is not None else None,
                    theta=self._float(row.get("theta")) if row.get("theta") is not None else None,
                    vega=self._float(row.get("vega")) if row.get("vega") is not None else None,
                )
            )
        return {symbol: tuple(items) for symbol, items in grouped.items()}


# Backward-compatible name used by the superseded package.
OptionHistoryDataAdapter = RepositoryOptionsDataAdapter
