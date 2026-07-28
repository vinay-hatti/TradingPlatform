from trading_ai.paper_trading.automated_order_handoff import (
    AutomatedPaperOrderCandidate,
    AutomatedPortfolioExposureEngine,
)


def candidate(limit_price=100.0, quantity=1.0):
    return AutomatedPaperOrderCandidate(
        candidate_id="c1",
        portfolio_id="PAPER-PRIMARY",
        symbol="AAPL",
        asset_class="EQUITY",
        side="BUY",
        quantity=quantity,
        limit_price=limit_price,
        institutional_allowed=True,
        risk_gateway_allowed=True,
        decision_score=80,
        probability=0.7,
        metadata={"sector": "TECHNOLOGY"},
    )


def exposure(**updates):
    value = {
        "net_liquidation_value": 100000,
        "cash_balance": 90000,
        "capital_committed": 10000,
        "open_position_count": 2,
        "by_symbol": [],
        "by_sector": [{"key": "TECHNOLOGY", "capital_pct": 10}],
    }
    value.update(updates)
    return value


def test_exposure_gate_allows_small_order():
    result = AutomatedPortfolioExposureEngine().assess(candidate(), exposure())
    assert result.allowed is True
    assert result.projected_capital_utilization_pct == 10.1


def test_exposure_gate_blocks_large_incremental_order():
    result = AutomatedPortfolioExposureEngine().assess(
        candidate(limit_price=1000, quantity=10),
        exposure(),
    )
    assert result.allowed is False
    assert "INCREMENTAL_ORDER_SIZE_EXCEEDED" in result.rejection_reasons


def test_exposure_gate_blocks_symbol_concentration():
    result = AutomatedPortfolioExposureEngine().assess(
        candidate(limit_price=2000, quantity=1),
        exposure(by_symbol=[{"key": "AAPL", "capital_pct": 19.0}]),
    )
    assert result.allowed is False
    assert "PROJECTED_SYMBOL_EXPOSURE_EXCEEDED" in result.rejection_reasons
