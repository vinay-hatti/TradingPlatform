from trading_ai.scanner.engine import ScannerEngine
from trading_ai.options.engine import OptionsEngineV2


def main():

    scanner = ScannerEngine()
    options = OptionsEngineV2()

    results = scanner.run_scan()

    print("\nHIGH QUALITY TRADES:\n")

    for r in results[:10]:

        trade = options.build_trade(
            symbol=r["symbol"],
            price=r["price"],
            score=r["score"]
        )

        if trade:
            print(trade)


if __name__ == "__main__":
    main()
