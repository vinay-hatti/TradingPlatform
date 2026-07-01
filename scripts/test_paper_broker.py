from trading_ai.execution.paper_broker import PaperBroker


def main():

    broker = PaperBroker(initial_cash=100000.0)

    order = broker.submit_order(
        symbol="AAPL",
        signal="CALL",
        strategy="LONG_CALL",
        strike=330.0,
        expiry="2028-01-21",
        quantity=1,
        price=44.59,
    )

    print("Order:", order)
    print("Summary:", broker.summary())


if __name__ == "__main__":
    main()
