import yfinance as yf


class OptionChain:

    def get_chain(self, symbol: str, expiration: str):

        t = yf.Ticker(symbol)

        chain = t.option_chain(expiration)

        return {"calls": chain.calls, "puts": chain.puts}

    def expirations(self, symbol: str):
        return yf.Ticker(symbol).options
