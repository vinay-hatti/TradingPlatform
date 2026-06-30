from trading_ai.database.repositories.base import BaseRepository
from trading_ai.database.models import PriceHistory


class PriceHistoryRepository(BaseRepository):

    def upsert(self, record: dict):

        obj = PriceHistory(**record)

        self.session.merge(obj)
        self.session.commit()

        return obj

    def get_latest(self, symbol: str):

        return (
            self.session.query(PriceHistory)
            .filter(PriceHistory.symbol == symbol)
            .order_by(PriceHistory.date.desc())
            .first()
        )
