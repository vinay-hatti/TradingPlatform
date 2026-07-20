from __future__ import annotations

from types import SimpleNamespace

from trading_ai.research_workstation.scanner.institutional_decision_adapter import (
    InstitutionalDecisionEngineAdapter,
)
from trading_ai.research_workstation.scanner.institutional_request_factory import (
    InstitutionalDecisionInputBundle,
)
from trading_ai.research_workstation.scanner.institutional_scanner_policy import (
    InstitutionalScannerFilterPolicy,
)
from trading_ai.research_workstation.scanner.institutional_scanner_service import (
    InstitutionalScannerDecisionService,
)
from trading_ai.research_workstation.scanner.market_scanner_profile import (
    MarketCandidateProfile,
)


class FakeInstitutionalService:
    def run(self, request):
        decision = SimpleNamespace(
            decision_id="decision-AAA",
            symbol="AAA",
            strategy="BULL_PUT_SPREAD",
            action="ENTER",
            readiness="READY",
            allowed=True,
            selected=True,
            rank=1,
            ranking_score=92.0,
            strategy_score=90.0,
            expected_profit=250.0,
            maximum_loss=500.0,
            probability_profile=SimpleNamespace(
                probability_of_profit=0.78,
                expected_return_on_capital=0.22,
            ),
            probability_calibration_profile=SimpleNamespace(
                calibrated_probability=0.81,
            ),
            market_regime_profile=SimpleNamespace(
                confidence_score=88.0,
            ),
            execution_profile=SimpleNamespace(
                execution_score=91.0,
            ),
            distribution_risk_profile=SimpleNamespace(
                tail_risk_score=18.0,
                tail_risk_grade="A",
            ),
            recommended_position_size_pct=2.5,
            stop_loss_pct=-25.0,
            take_profit_pct=60.0,
            warnings=[],
            rejection_reasons=[],
            metadata={},
        )
        return SimpleNamespace(
            decisions=[decision],
            total_symbols=1,
            processed_symbols=1,
            selected_count=1,
            valid=True,
            overall_readiness="READY",
            overall_action="ENTER",
            warnings=[],
            errors=[],
            metadata={"test": True},
        )


def candidate() -> MarketCandidateProfile:
    return MarketCandidateProfile(
        symbol="AAA",
        price=100.0,
        average_volume=2_000_000,
        option_volume=10_000,
        open_interest=50_000,
        spread_pct=0.05,
        iv_rank=70.0,
        iv_percentile=75.0,
        atr_pct=2.0,
        trend_score=80.0,
        momentum_score=75.0,
        liquidity_score=90.0,
        volatility_score=70.0,
        regime_score=85.0,
        decision_confidence=0.0,
        expected_return=0.0,
        risk_score=50.0,
        reward_risk_ratio=0.0,
        signal="CALL",
        regime="TREND_UP",
    )


def main() -> None:
    service = InstitutionalScannerDecisionService(
        adapter=InstitutionalDecisionEngineAdapter(
            service=FakeInstitutionalService()
        ),
        filter_policy=InstitutionalScannerFilterPolicy(
            minimum_probability_of_profit=0.70,
            minimum_expected_return=0.15,
            minimum_reward_risk_ratio=0.40,
            minimum_decision_confidence=80.0,
            require_allowed=True,
            require_selected=True,
        ),
    )

    enriched, run = service.enrich(
        candidates=(candidate(),),
        inputs=InstitutionalDecisionInputBundle(
            price_history_by_symbol={"AAA": [{"close": 100.0}]},
            option_chain_by_symbol={"AAA": [{"strike": 100.0}]},
        ),
    )

    assert run.valid is True, run
    assert run.selected_count == 1, run
    assert len(enriched) == 1, enriched

    result = enriched[0]
    assert result.decision_confidence == 92.0, result
    assert result.expected_return == 0.22, result
    assert result.reward_risk_ratio == 0.5, result
    assert result.risk_score == 18.0, result

    institutional = result.metadata["institutional_decision"]

    assert institutional["strategy"] == "BULL_PUT_SPREAD", institutional
    assert institutional["probability_of_profit"] == 0.78, institutional
    assert institutional["calibrated_probability"] == 0.81, institutional
    assert institutional["tail_risk_grade"] == "A", institutional

    # Deterministic score from the default policy:
    # probability       81.0 * 0.35 = 28.350
    # expected return   22.0 * 0.20 =  4.400
    # reward/risk       12.5 * 0.15 =  1.875
    # regime            88.0 * 0.15 = 13.200
    # execution         91.0 * 0.10 =  9.100
    # tail quality      82.0 * 0.05 =  4.100
    # total                          = 61.025
    assert institutional["institutional_score"] == 61.025, institutional

    print(
        "All Milestone 34 Phase 1 Step 4 institutional integration "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
