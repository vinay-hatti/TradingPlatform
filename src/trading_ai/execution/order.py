from dataclasses import dataclass, asdict
from datetime import datetime
from uuid import uuid4


@dataclass
class PaperOrder:
    id: str
    symbol: str
    signal: str
    strategy: str
    strike: float
    expiry: str
    quantity: int
    price: float
    implied_volatility: float
    status: str
    created_at: str

    @classmethod
    def create(
        cls,
        symbol,
        signal,
        strategy,
        strike,
        expiry,
        quantity,
        price,
        implied_volatility=0.25,
    ):
        return cls(
            id=str(uuid4()),
            symbol=symbol,
            signal=signal,
            strategy=strategy,
            strike=float(strike),
            expiry=str(expiry),
            quantity=int(quantity),
            price=float(price),
            implied_volatility=float(implied_volatility),
            status="FILLED",
            created_at=datetime.now().isoformat(),
        )

    def to_dict(self):
        return asdict(self)
