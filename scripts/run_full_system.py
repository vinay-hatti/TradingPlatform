from trading_ai.scanner.engine import ScannerEngine
from trading_ai.options.engine import OptionsEngineV2
from trading_ai.portfolio.portfolio_engine import PortfolioEngine


def main():

    scanner = ScannerEngine()
    options = OptionsEngineV2()
    portfolio = PortfolioEngine(account_value=100000)

    results = scanner.run_scan()

    print("\nBUILDING PORTFOLIO...\n")

    for r in results:

        trade = options.build_trade(
            symbol=r["symbol"],
            price=r["price"],
            score=r["score"]
        )

        if trade:

            position = portfolio.add_trade(trade)

            if position:
                print(position)

    print("\nPORTFOLIO SUMMARY:\n")
    print(portfolio.summary())


if __name__ == "__main__":
    main()
