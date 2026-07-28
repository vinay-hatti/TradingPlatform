from trading_ai.paper_trading.automated_order_handoff import (
    AutomatedPaperOrderCandidate,
    AutomatedPaperOrderFactory,
    AutomatedPaperOrderHandoffEngine,
)


def candidate(**overrides):
    values = dict(
        candidate_id="candidate-001",
        portfolio_id="PAPER-PRIMARY",
        symbol="AAPL",
        asset_class="EQUITY",
        side="BUY",
        quantity=1,
        order_type="LIMIT",
        time_in_force="DAY",
        limit_price=1.0,
        institutional_allowed=True,
        risk_gateway_allowed=True,
        decision_score=80.0,
        probability=0.70,
        primary_exchange="NASDAQ",
    )
    values.update(overrides)
    return AutomatedPaperOrderCandidate(**values)


def test_approved_candidate_maps_deterministically():
    value = candidate()
    assessment = AutomatedPaperOrderHandoffEngine().assess(value)
    assert assessment.allowed is True
    factory = AutomatedPaperOrderFactory()
    first = factory.identifiers(value)
    second = factory.identifiers(value)
    assert first == second
    request = factory.ibkr_request(value, broker_account_id="DU123")
    assert request.security_type == "STK"
    assert request.order_type == "LMT"
    assert request.side == "BUY"


def test_rejected_without_governance_approvals():
    assessment = AutomatedPaperOrderHandoffEngine().assess(
        candidate(institutional_allowed=False, risk_gateway_allowed=False)
    )
    assert assessment.allowed is False
    assert "INSTITUTIONAL_DECISION_REJECTED" in assessment.rejection_reasons
    assert "RISK_GATEWAY_REJECTED" in assessment.rejection_reasons


def test_option_contract_fields_are_required():
    assessment = AutomatedPaperOrderHandoffEngine().assess(
        candidate(asset_class="OPTION")
    )
    assert assessment.allowed is False
    assert "OPTION_EXPIRY_REQUIRED" in assessment.rejection_reasons
    assert "OPTION_STRIKE_REQUIRED" in assessment.rejection_reasons
    assert "OPTION_RIGHT_REQUIRED" in assessment.rejection_reasons
