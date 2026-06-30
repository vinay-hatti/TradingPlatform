from trading_ai.market.downloader import MarketDownloader


def main():
    downloader = MarketDownloader()
    downloader.run_bulk_download()
    print("Market ingestion complete")


if __name__ == "__main__":
    main()
