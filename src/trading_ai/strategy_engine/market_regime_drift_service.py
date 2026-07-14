from .market_regime_drift_engine import MarketRegimeDriftEngine
from .market_regime_drift_policy import MarketRegimeDriftPolicy


class MarketRegimeDriftService:
    def __init__(self, policy: MarketRegimeDriftPolicy | None = None, engine: MarketRegimeDriftEngine | None = None):
        self.engine = engine or MarketRegimeDriftEngine(policy)

    def analyze(self, reference_profiles, recent_profiles):
        return self.engine.analyze(reference_profiles, recent_profiles)
