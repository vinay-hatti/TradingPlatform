from .providers.yahoo import YahooProvider


class MarketRepository:

    def __init__(self):

        self.provider = YahooProvider()

    def history(self, ticker):

        return self.provider.history(ticker)

    def quote(self, ticker):

        return self.provider.quote(ticker)
