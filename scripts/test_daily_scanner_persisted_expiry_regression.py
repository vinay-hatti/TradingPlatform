from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from trading_ai.daily.scanner import DailyScanner
from trading_ai.options.live_snapshot import LiveOptionDataError


def _failing_proxy_selector():
    return SimpleNamespace(
        select=lambda **_: (_ for _ in ()).throw(
            AssertionError("proxy expiry selector must not run for persisted contracts")
        )
    )


def test_persisted_contract_keeps_real_expiry_and_ticker():
    live = SimpleNamespace(
        contract_ticker="O:BAC260918C00062500",
        expiration_date="2026-09-18",
    )
    ticker, expiry, dte, source = DailyScanner._resolve_candidate_expiry(
        symbol="BAC",
        as_of=date(2026, 7, 23),
        selected_live_contract=live,
        option_data_source="POLYGON_PERSISTED",
        expiry_selector=_failing_proxy_selector(),
        valuation_date="2026-07-23",
        proxy_dte=90,
    )
    assert ticker == "O:BAC260918C00062500"
    assert expiry == "2026-09-18"
    assert dte == 57
    assert source == "LIVE_LISTED_CONTRACT"
    assert expiry != "2026-10-23"


def test_persisted_contract_missing_ticker_fails_closed():
    live = SimpleNamespace(contract_ticker="", expiration_date="2026-09-18")
    try:
        DailyScanner._resolve_candidate_expiry(
            symbol="BAC",
            as_of=date(2026, 7, 23),
            selected_live_contract=live,
            option_data_source="POLYGON_PERSISTED",
            expiry_selector=_failing_proxy_selector(),
            valuation_date="2026-07-23",
            proxy_dte=90,
        )
    except LiveOptionDataError as exc:
        assert "missing its contract ticker" in str(exc)
    else:
        raise AssertionError("missing persisted ticker must fail closed")


def test_proxy_mode_still_uses_standard_friday_selector():
    selector = SimpleNamespace(
        select=lambda **_: SimpleNamespace(
            expiration_iso="2026-10-23",
            actual_dte=92,
            source="STANDARD_FRIDAY_PROXY",
        )
    )
    ticker, expiry, dte, source = DailyScanner._resolve_candidate_expiry(
        symbol="BAC",
        as_of=date(2026, 7, 23),
        selected_live_contract=None,
        option_data_source="PROXY",
        expiry_selector=selector,
        valuation_date="2026-07-23",
        proxy_dte=90,
    )
    assert ticker == ""
    assert expiry == "2026-10-23"
    assert dte == 92
    assert source == "STANDARD_FRIDAY_PROXY"


def main():
    test_persisted_contract_keeps_real_expiry_and_ticker()
    test_persisted_contract_missing_ticker_fails_closed()
    test_proxy_mode_still_uses_standard_friday_selector()
    print("Daily scanner persisted-expiry regression tests passed.")


if __name__ == "__main__":
    main()
