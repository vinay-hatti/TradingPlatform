from concurrent.futures import ThreadPoolExecutor
from trading_ai.market.universe import SP500
from trading_ai.market.service import MarketService


class MarketDownloader:

    def __init__(self):
        self.service = MarketService()

    def run_bulk_download(self):

        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(self.service.save_history, SP500)
