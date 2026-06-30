class ExposureTracker:

    def __init__(self):

        self.sectors = {
            "tech": ["AAPL", "MSFT", "NVDA", "META", "GOOGL"],
            "semi": ["NVDA", "AMD", "INTC", "AVGO"],
        }

    def sector_exposure(self, portfolio):

        exposure = {}

        for p in portfolio:

            symbol = p["symbol"]

            for sector, tickers in self.sectors.items():

                if symbol in tickers:
                    exposure[sector] = exposure.get(sector, 0) + p["risk"]

        return exposure
