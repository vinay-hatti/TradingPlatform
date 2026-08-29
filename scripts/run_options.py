from trading_ai.scanner.engine import ScannerEngine
from trading_ai.options.engine import OptionsEngine


def main():

    scanner = ScannerEngine()
    options = OptionsEngine()

    results = scanner.run_scan()

    print("\nOPTIONS SETUPS:\n")

    for r in results[:5]:

        trade = options.build_trade(
            symbol=r["symbol"],
            price=r["price"],
            score=r["score"]
        )

        if trade:
            print(trade)


if __name__ == "__main__":
    main()
