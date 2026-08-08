from dataclasses import dataclass

@dataclass(frozen=True)
class EventSyncPolicy:
    horizon_months: int = 6
    timeout_seconds: float = 45.0
    user_agent: str = 'TradingPlatform-M69.6/1.0 (governed event intelligence)'
    earnings_horizon: str = '6month'
    preserve_unseen_days: int = 14
    requested_weights: tuple[float,float,float] = (0.55,0.30,0.15)
