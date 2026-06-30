from sqlalchemy import Column, Date, Float, String

from trading_ai.database.base import Base


class MarketFeature(Base):
    __tablename__ = "market_features"

    symbol = Column(String(16), primary_key=True)
    date = Column(Date, primary_key=True)

    ema20 = Column(Float)
    ema50 = Column(Float)
    ema200 = Column(Float)

    rsi14 = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)

    atr14 = Column(Float)
    bollinger_width = Column(Float)
    hv20 = Column(Float)

    volume_sma20 = Column(Float)
    volume_ratio = Column(Float)

    vwap = Column(Float)
    price_vs_vwap = Column(Float)

    market_regime = Column(String(32))
