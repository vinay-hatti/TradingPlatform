from .polygon import PolygonProvider


class MarketRepository:
    def __init__(self, provider: PolygonProvider | None = None):
        self.provider = provider or PolygonProvider()

    def history(self, ticker, *args, **kwargs):
        return self.provider.history(ticker, *args, **kwargs)

    def quote(self, ticker):
        return self.provider.quote(ticker)
