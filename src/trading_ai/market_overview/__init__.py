__all__ = ["MarketOverviewService", "MarketOverviewSnapshot"]

def __getattr__(name):
    if name == "MarketOverviewService":
        from .service import MarketOverviewService
        return MarketOverviewService
    if name == "MarketOverviewSnapshot":
        from .contracts import MarketOverviewSnapshot
        return MarketOverviewSnapshot
    raise AttributeError(name)
