__all__=["MarketIntelligenceService","MarketIntelligenceSnapshot"]
def __getattr__(name):
    if name=='MarketIntelligenceService':
        from .service import MarketIntelligenceService
        return MarketIntelligenceService
    if name=='MarketIntelligenceSnapshot':
        from .contracts import MarketIntelligenceSnapshot
        return MarketIntelligenceSnapshot
    raise AttributeError(name)
