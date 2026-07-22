from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class PriceHistoryCoverageRecord:
    symbol: str
    row_count: int
    trading_day_count: int
    earliest_date: date | None
    latest_date: date | None


class PriceHistoryCoverageRepository:
    """Read-only aggregate repository for canonical price-history coverage."""

    def __init__(
        self,
        bind: Engine | Session,
        *,
        table_name: str = "price_history",
        schema: str | None = None,
    ) -> None:
        self._bind = bind
        self.table_name = table_name
        self.schema = schema

    def aggregate(self, symbols: Iterable[str]) -> dict[str, PriceHistoryCoverageRecord]:
        selected = tuple(dict.fromkeys(
            str(symbol or "").strip().upper()
            for symbol in symbols
            if str(symbol or "").strip()
        ))
        if not selected:
            return {}

        engine = self._engine()
        table = Table(
            self.table_name,
            MetaData(),
            schema=self.schema,
            autoload_with=engine,
        )
        self._validate_columns(table)

        statement = (
            select(
                table.c.symbol,
                func.count().label("row_count"),
                func.count(func.distinct(table.c.date)).label("trading_day_count"),
                func.min(table.c.date).label("earliest_date"),
                func.max(table.c.date).label("latest_date"),
            )
            .where(func.upper(table.c.symbol).in_(selected))
            .group_by(table.c.symbol)
        )

        output: dict[str, PriceHistoryCoverageRecord] = {}
        if isinstance(self._bind, Session):
            rows = self._bind.execute(statement)
            for row in rows:
                record = self._record(row)
                output[record.symbol] = record
            return output

        with engine.connect() as connection:
            for row in connection.execute(statement):
                record = self._record(row)
                output[record.symbol] = record
        return output

    def _engine(self) -> Engine:
        if isinstance(self._bind, Session):
            return self._bind.get_bind()
        return self._bind

    @staticmethod
    def _validate_columns(table: Table) -> None:
        missing = {"symbol", "date"} - set(table.c.keys())
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"price-history table is missing required columns: {names}")

    @staticmethod
    def _record(row) -> PriceHistoryCoverageRecord:
        mapping = row._mapping
        return PriceHistoryCoverageRecord(
            symbol=str(mapping["symbol"]).strip().upper(),
            row_count=int(mapping["row_count"] or 0),
            trading_day_count=int(mapping["trading_day_count"] or 0),
            earliest_date=_coerce_date(mapping["earliest_date"]),
            latest_date=_coerce_date(mapping["latest_date"]),
        )


def _coerce_date(value) -> date | None:
    if value is None or isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])
