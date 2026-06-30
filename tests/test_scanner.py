from trading_ai.app.bootstrap import container


def test_scan():

    scanner = container.scanner

    trades = scanner.scan(
        symbols=["AAPL"],
        start="2026-01-01",
        end="2026-06-01",
    )

    assert len(trades) == 1
