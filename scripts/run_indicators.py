from trading_ai.market.yahoo import YahooProvider
from trading_ai.indicators.engine import IndicatorEngine


def main():

    provider = YahooProvider()
    engine = IndicatorEngine()

    df = provider.history("AAPL", period="6mo")

    df = engine.run(df)

    print(df.tail())


if __name__ == "__main__":
    main()
