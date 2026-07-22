from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from trading_ai.market.models import PriceHistory

from .models import PriceBar


class PriceHistoryBulkRepository:
    def __init__(self, session) -> None:
        self.session = session

    def coverage(self, symbols: Iterable[str]) -> dict[str, tuple[int, date | None]]:
        selected = tuple(dict.fromkeys(symbols))
        if not selected:
            return {}
        output: dict[str, tuple[int, date | None]] = {}
        chunk_size = 1000
        for offset in range(0, len(selected), chunk_size):
            chunk = selected[offset:offset + chunk_size]
            stmt = (
                select(PriceHistory.symbol, func.count(), func.max(PriceHistory.date))
                .where(PriceHistory.symbol.in_(chunk))
                .group_by(PriceHistory.symbol)
            )
            for symbol, count, latest in self.session.execute(stmt):
                output[str(symbol)] = (int(count), latest)
        return output

    def upsert(self, bars: Iterable[PriceBar]) -> int:
        rows = [
            {"symbol": b.symbol, "date": b.date, "open": b.open, "high": b.high,
             "low": b.low, "close": b.close, "volume": b.volume}
            for b in bars
        ]
        if not rows:
            return 0
        dialect = self.session.get_bind().dialect.name
        if dialect == "postgresql":
            stmt = pg_insert(PriceHistory).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=[PriceHistory.symbol, PriceHistory.date],
                set_={key: getattr(stmt.excluded, key) for key in ("open", "high", "low", "close", "volume")},
            )
            self.session.execute(stmt)
        elif dialect == "sqlite":
            stmt = sqlite_insert(PriceHistory).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "date"],
                set_={key: getattr(stmt.excluded, key) for key in ("open", "high", "low", "close", "volume")},
            )
            self.session.execute(stmt)
        else:
            for row in rows:
                self.session.merge(PriceHistory(**row))
        self.session.commit()
        return len(rows)
