from trading_ai.market.downloader import RequestPacer


def test_rate_limit_is_global_and_adaptive():
    pacer = RequestPacer(1.0, rate_limit_floor_seconds=15.0)
    state = pacer.register_rate_limit(60.0)
    assert state["events"] == 1
    assert state["effective_interval_seconds"] == 15.0
    state = pacer.register_rate_limit(60.0)
    assert state["events"] == 2
    assert state["effective_interval_seconds"] == 30.0
