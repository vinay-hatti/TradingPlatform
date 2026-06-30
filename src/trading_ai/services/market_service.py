from trading_ai.database import get_session
from trading_ai.database.repositories import PriceHistoryRepository
from trading_ai.market.dto import PriceDTO


class MarketService:

    def latest_price(self, symbol: str):

        with get_session() as session:

            repo = PriceHistoryRepository(session)

            price = repo.latest(symbol)

            if not price:
                return None

            # ✅ Convert ORM → dict HERE (service layer only)
            return PriceDTO(
                symbol=price.symbol,
                date=price.date,
                open=price.open,
                high=price.high,
                low=price.low,
                close=price.close,
                volume=price.volume,
            )


#            return {
#                "symbol": price.symbol,
#                "date": str(price.date),
#                "open": price.open,
#                "high": price.high,
#                "low": price.low,
#                "close": price.close,
#                "volume": price.volume,
#            }
