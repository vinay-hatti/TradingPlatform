from polygon import RESTClient
from trading_ai.config import settings

def main():
    if not settings.polygon_api_key:
        raise ValueError("POLYGON_API_KEY not set")

    client = RESTClient(settings.polygon_api_key)

    ticker = client.get_ticker_details("AAPL")
    print("Connected:", ticker.name)


if __name__ == "__main__":
    main()
