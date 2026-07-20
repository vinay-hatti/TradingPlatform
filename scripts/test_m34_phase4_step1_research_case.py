from datetime import datetime, timezone

from trading_ai.research_workstation.research_cases import (
    ResearchCaseEngine,
    research_case_payload,
)


def main() -> None:
    profile = ResearchCaseEngine().build(
        case_id="CASE-001",
        symbol="AAPL",
        strategy_name="BULL_PUT_SPREAD",
        title="AAPL defined-risk bullish thesis",
        primary_thesis=(
            "Stable earnings expectations and constructive momentum "
            "support a defined-risk bullish options structure."
        ),
        time_horizon="30-45 DAYS",
        review_date="2026-07-26",
        confidence_score=0.78,
        scenarios=(
            {
                "scenario_id": "BASE",
                "name": "Base Case",
                "scenario_type": "BASE",
                "probability": 0.50,
                "expected_return_pct": 0.10,
                "expected_volatility_pct": 0.24,
                "expected_drawdown_pct": 0.05,
                "expected_holding_days": 21,
                "thesis": "Price remains above primary support.",
                "catalysts": ("Stable earnings revisions",),
                "risks": ("Broad market weakness",),
                "invalidation_conditions": (
                    "Daily close below primary support",
                ),
                "recommended_action": "ENTER",
            },
            {
                "scenario_id": "BULL",
                "name": "Bull Case",
                "scenario_type": "BULL",
                "probability": 0.25,
                "expected_return_pct": 0.20,
                "expected_volatility_pct": 0.28,
                "expected_drawdown_pct": 0.03,
                "expected_holding_days": 14,
                "thesis": "Upside momentum accelerates.",
                "catalysts": ("Positive guidance",),
                "risks": ("Volatility compression",),
                "invalidation_conditions": (
                    "Momentum confirmation fails",
                ),
                "recommended_action": "ENTER",
            },
            {
                "scenario_id": "BEAR",
                "name": "Bear Case",
                "scenario_type": "BEAR",
                "probability": 0.25,
                "expected_return_pct": -0.15,
                "expected_volatility_pct": 0.36,
                "expected_drawdown_pct": 0.18,
                "expected_holding_days": 10,
                "thesis": "Support fails after a macro shock.",
                "catalysts": ("Risk-off repricing",),
                "risks": ("Gap risk",),
                "invalidation_conditions": (
                    "Price reclaims failed support",
                ),
                "recommended_action": "AVOID",
            },
        ),
        evidence=(
            {
                "evidence_id": "E-001",
                "category": "TECHNICAL",
                "description": "Price remains above trend support.",
                "source": "FeaturePipeline",
                "observed_at": datetime(
                    2026, 7, 19, tzinfo=timezone.utc
                ),
                "reliability_score": 0.85,
                "supports_thesis": True,
            },
        ),
        assumptions=(
            {
                "assumption_id": "A-001",
                "description": "No material earnings revision.",
                "importance": "HIGH",
                "confidence": 0.70,
                "validation_method": "Monitor analyst revisions.",
                "invalidation_condition": (
                    "Consensus EPS falls more than 5%."
                ),
            },
        ),
    )

    assert profile.status == "READY"
    assert profile.research_score == 100.0
    assert profile.research_grade == "A"
    assert profile.scenario_probability_total == 1.0
    assert profile.expected_return_pct == 0.0625
    assert len(profile.scenarios) == 3
    assert not profile.warnings
    assert not profile.rejection_reasons
    assert profile.metadata["phase"] == 4

    payload = research_case_payload(profile)
    assert payload["case_id"] == "CASE-001"
    assert payload["scenarios"][0]["scenario_type"] == "BASE"

    print(
        "All Milestone 34 Phase 4 Step 1 research-case "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
