from .contracts import TrendHorizon, TrendSnapshot
from .engine import TrendIntelligenceEngine

__all__ = ["TrendHorizon", "TrendSnapshot", "TrendIntelligenceEngine", "TrendIntelligenceRepository", "TrendIntelligenceService"]

def __getattr__(name):
    if name == "TrendIntelligenceRepository":
        from .repository import TrendIntelligenceRepository
        return TrendIntelligenceRepository
    if name == "TrendIntelligenceService":
        from .service import TrendIntelligenceService
        return TrendIntelligenceService
    raise AttributeError(name)
