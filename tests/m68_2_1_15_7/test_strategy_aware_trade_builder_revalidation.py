from pathlib import Path

from trading_ai.advanced_trade_builder.contracts import LegSide, OptionRight, TradeLeg
from trading_ai.advanced_trade_builder.service import AdvancedTradeBuilderService

ROOT = Path(__file__).resolve().parents[2]


def _leg(side: LegSide, strike: float, expiry: str, price: float) -> TradeLeg:
    return TradeLeg(
        side=side,
        quantity=1,
        option_right=OptionRight.CALL,
        strike=strike,
        expiry=expiry,
        limit_price=price,
        option_symbol=f"O:TEST{expiry.replace('-', '')}C{int(strike * 1000):08d}",
    )


def test_diagonal_trade_builder_validation_requires_two_expiries():
    legs = (
        _leg(LegSide.BUY, 380, "2026-10-16", 8.00),
        _leg(LegSide.SELL, 390, "2026-09-18", 2.00),
    )
    *_, checks = AdvancedTradeBuilderService.economics(
        legs, 1_000_000, 5.0, strategy="CALL_DIAGONAL"
    )
    assert checks["two_expiries"] is True
    assert "single_expiry" not in checks
    assert checks["valid"] is True


def test_m62_handoff_passes_selected_strategy_into_trade_builder_economics():
    source = (ROOT / "src/trading_ai/institutional_options/handoff.py").read_text()
    assert "strategy=strategy.strategy" in source
    assert "AdvancedTradeBuilderService.economics(" in source


def test_revalidate_endpoint_returns_explicit_outcome_metadata():
    source = (ROOT / "src/trading_ai/advanced_trade_builder/router.py").read_text()
    for token in (
        "previous_state=previous_state",
        "previous_version=previous_version",
        "current_state=refreshed.state",
        "current_version=refreshed.version",
        "failed_checks=failed",
        "validation_changed=previous_validation!=current_validation",
    ):
        assert token in source


def test_workstation_surfaces_two_expiry_rule_and_versioned_revalidation_result():
    source = (ROOT / "ui/workstation/src/AdvancedTradeBuilderPage.tsx").read_text()
    assert "case 'two_expiries':" in source
    assert "Exactly 2 unique expiries for calendar/diagonal strategies" in source
    assert "revalidation passed (v${priorVersion} → v${currentVersion})" in source
    assert "Failed: ${failedChecks.join(' · ')}" in source
