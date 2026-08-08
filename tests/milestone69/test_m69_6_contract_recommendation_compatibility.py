from trading_ai.institutional_options.domain import (
    ContractSide,
    deserialize_contract_recommendation,
    serialize_domain,
)


def _payload():
    return {
        "contract_recommendation_id": "contract-1",
        "strategy_candidate_id": "strategy-1",
        "opportunity_id": "opportunity-1",
        "option_snapshot_id": "snapshot-1",
        "legs": [{
            "leg_id": "leg-1", "side": "BUY", "option_type": "CALL",
            "option_symbol": "O:AAPL260918C00200000", "expiry": "2026-09-18",
            "strike": 200.0,
        }],
        "strategy": "LONG_CALL",
        "executable": True,
        "validation_reasons": ["OK"],
        "rejection_reasons": [],
        "optimization_scores": {"overall_contract_score": 88.0},
        "option_valuation_intelligence": {"classification": "UNDERPRICED", "edge_score": 73.0},
    }


def test_m69_enriched_contract_payload_rehydrates_without_constructor_failure():
    contract = deserialize_contract_recommendation(_payload())
    assert contract.legs[0].side is ContractSide.BUY
    assert contract.option_valuation_intelligence["classification"] == "UNDERPRICED"
    assert contract.validation_reasons == ("OK",)


def test_unknown_future_intelligence_is_preserved_in_extensions():
    payload = _payload() | {"portfolio_allocation_intelligence": {"fractional_kelly": 0.12}}
    contract = deserialize_contract_recommendation(payload)
    assert contract.intelligence_extensions["portfolio_allocation_intelligence"]["fractional_kelly"] == 0.12
    serialized = serialize_domain(contract)
    assert serialized["intelligence_extensions"]["portfolio_allocation_intelligence"]["fractional_kelly"] == 0.12
