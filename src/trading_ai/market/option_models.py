from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from trading_ai.database.base import Base


class OptionContractHistory(Base):
    __tablename__ = "option_contract_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    underlying_symbol: Mapped[str] = mapped_column(String, index=True)
    option_symbol: Mapped[str] = mapped_column(String, index=True)

    quote_date: Mapped[Date] = mapped_column(Date, index=True)
    expiry: Mapped[Date] = mapped_column(Date, index=True)

    option_type: Mapped[str] = mapped_column(String)  # CALL / PUT
    strike: Mapped[float] = mapped_column(Float)

    bid: Mapped[float] = mapped_column(Float, default=0.0)
    ask: Mapped[float] = mapped_column(Float, default=0.0)
    mid: Mapped[float] = mapped_column(Float, default=0.0)
    last: Mapped[float] = mapped_column(Float, default=0.0)

    volume: Mapped[int] = mapped_column(Integer, default=0)
    open_interest: Mapped[int] = mapped_column(Integer, default=0)

    implied_volatility: Mapped[float] = mapped_column(Float, default=0.0)

    delta: Mapped[float] = mapped_column(Float, default=0.0)
    gamma: Mapped[float] = mapped_column(Float, default=0.0)
    theta: Mapped[float] = mapped_column(Float, default=0.0)
    vega: Mapped[float] = mapped_column(Float, default=0.0)
    rho: Mapped[float] = mapped_column(Float, default=0.0)
