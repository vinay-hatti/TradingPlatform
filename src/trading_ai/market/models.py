from sqlalchemy import Column, Date, Float, String

from trading_ai.database.base import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    symbol = Column(String(16), primary_key=True)
    date = Column(Date, primary_key=True)

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
