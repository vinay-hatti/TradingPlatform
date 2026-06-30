from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import select

from trading_ai.database.repositories.base import BaseRepository

if TYPE_CHECKING:
    from trading_ai.market.models import PriceHistory


class PriceHistoryRepository(BaseRepository):

    def save(self, price: "PriceHistory") -> "PriceHistory":
        self.session.add(price)
        return price

    def save_many(self, prices: list["PriceHistory"]) -> None:
        self.session.add_all(prices)

    def latest(self, symbol: str):

        from trading_ai.market.models import PriceHistory  # local import FIX

        stmt = (
            select(PriceHistory)
            .where(PriceHistory.symbol == symbol)
            .order_by(PriceHistory.date.desc())
            .limit(1)
        )

        return self.session.scalar(stmt)

    def get_range(self, symbol: str, start: date, end: date):

        from trading_ai.market.models import PriceHistory  # local import FIX

        stmt = (
            select(PriceHistory)
            .where(
                PriceHistory.symbol == symbol,
                PriceHistory.date >= start,
                PriceHistory.date <= end,
            )
            .order_by(PriceHistory.date)
        )

        return list(self.session.scalars(stmt))

    def delete_symbol(self, symbol: str):

        from trading_ai.market.models import PriceHistory

        stmt = select(PriceHistory).where(PriceHistory.symbol == symbol)

        rows = self.session.scalars(stmt)

        for row in rows:
            self.session.delete(row)
