from dataclasses import dataclass


@dataclass
class ExpectedMoveSource:
    source: str

    horizon_days: int

    move_dollars: float
    move_pct: float

    weight: float
    available: bool

    reason: str = ""
