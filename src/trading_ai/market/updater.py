from src.database.database import Session

from .models import PriceHistory

from .downloader import Downloader


class MarketUpdater:

    def __init__(self):

        self.session = Session()

        self.downloader = Downloader()

    def update(self, ticker):

        df = self.downloader.download(ticker)

        for idx, row in df.iterrows():

            price = PriceHistory(
                symbol=ticker,
                date=idx.date(),
                open=float(row["Open"].iloc[0]),
                high=float(row["High"].iloc[0]),
                low=float(row["Low"].iloc[0]),
                close=float(row["Close"].iloc[0]),
                volume=float(row["Volume"].iloc[0]),
            )

            self.session.merge(price)

        self.session.commit()
