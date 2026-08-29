from trading_ai.advanced_trade_builder.contracts import LegSide, OptionRight, TradeLeg
from trading_ai.advanced_trade_builder.service import AdvancedTradeBuilderService


def leg(side: LegSide, strike: float, expiry: str, price: float, right: OptionRight = OptionRight.CALL):
    return TradeLeg(
        side=side,
        quantity=1,
        option_right=right,
        strike=strike,
        expiry=expiry,
        limit_price=price,
        option_symbol=f"O:TEST{expiry.replace('-', '')}{right.value[0]}{int(strike*1000):08d}",
    )


def test_call_diagonal_requires_two_expiries_and_is_valid_when_distinct():
    legs = (
        leg(LegSide.BUY, 28, "2026-10-16", 4.00),
        leg(LegSide.SELL, 30, "2026-09-11", 0.83),
    )
    *_, max_profit, rr, _, _, checks = AdvancedTradeBuilderService.economics(
        legs, 1_000_000, 5.0, "CALL_DIAGONAL"
    )
    assert checks["two_expiries"] is True
    assert "single_expiry" not in checks
    assert checks["valid"] is True
    assert max_profit is None
    assert rr is None


def test_call_diagonal_rejects_same_expiry():
    legs = (
        leg(LegSide.BUY, 28, "2026-10-16", 4.00),
        leg(LegSide.SELL, 30, "2026-10-16", 0.83),
    )
    *_, checks = AdvancedTradeBuilderService.economics(
        legs, 1_000_000, 5.0, "CALL_DIAGONAL"
    )
    assert checks["two_expiries"] is False
    assert checks["valid"] is False


def test_call_calendar_requires_two_expiries():
    legs = (
        leg(LegSide.BUY, 28, "2026-10-16", 4.00),
        leg(LegSide.SELL, 28, "2026-09-11", 1.00),
    )
    *_, checks = AdvancedTradeBuilderService.economics(
        legs, 1_000_000, 5.0, "CALL_CALENDAR"
    )
    assert checks["two_expiries"] is True
    assert checks["valid"] is True


def test_vertical_still_requires_single_expiry():
    good = (
        leg(LegSide.BUY, 28, "2026-09-18", 2.00),
        leg(LegSide.SELL, 30, "2026-09-18", 1.00),
    )
    bad = (
        leg(LegSide.BUY, 28, "2026-10-16", 2.00),
        leg(LegSide.SELL, 30, "2026-09-18", 1.00),
    )
    *_, good_checks = AdvancedTradeBuilderService.economics(good, 1_000_000, 5.0, "BULL_CALL_SPREAD")
    *_, bad_checks = AdvancedTradeBuilderService.economics(bad, 1_000_000, 5.0, "BULL_CALL_SPREAD")
    assert good_checks["single_expiry"] is True
    assert good_checks["valid"] is True
    assert bad_checks["single_expiry"] is False
    assert bad_checks["valid"] is False


def test_put_diagonal_uses_two_expiry_rule():
    legs = (
        leg(LegSide.BUY, 28, "2026-10-16", 4.00, OptionRight.PUT),
        leg(LegSide.SELL, 26, "2026-09-11", 0.83, OptionRight.PUT),
    )
    *_, checks = AdvancedTradeBuilderService.economics(legs, 1_000_000, 5.0, "PUT_DIAGONAL")
    assert checks["two_expiries"] is True
    assert checks["valid"] is True
