from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.database.models import PriceHistory
from trading_ai.outcome_probability.engine import (
    GovernedOutcomeModelTrainer,
    OutcomeProbabilityRuntime,
)
from trading_ai.outcome_probability.features import (
    NUMERIC_FEATURES,
    PointInTimeFeatureBuilder,
)
from trading_ai.outcome_probability.labels import BarrierOutcomeLabeler
from trading_ai.outcome_probability.models import OutcomeProbabilityObservationModel
from trading_ai.outcome_probability.operator import result_exit_code
from trading_ai.outcome_probability.policy import OutcomeProbabilityPolicy
from trading_ai.outcome_probability.service import OutcomeProbabilityService
from trading_ai.stock_intelligence.decision_intelligence import (
    InstitutionalDecisionAssessment,
)
from trading_ai.stock_intelligence.models import StockScannerCandidateModel
from trading_ai.stock_intelligence.profile import StockIntelligenceProfile


def candidate_payload() -> dict:
    vector = {name: 70.0 for name in NUMERIC_FEATURES}
    vector.update({"relative_volume_1d": 1.4, "structural_reward_risk": 2.0})
    return {
        "symbol": "TEST",
        "snapshot_timestamp": "2026-01-02T21:00:00+00:00",
        "provider": "polygon",
        "direction": "STRONG_BULLISH",
        "alignment_score": 85,
        "scores": {"overall": 82, "confidence": 80, "primary_category": "ACCUMULATION_BREAKOUT"},
        "context": {"market_regime": "UPTREND", "gamma_regime": "NEGATIVE_GAMMA"},
        "breakout": {"confirmation": 82, "follow_through_probability": 74, "failure_probability": 20},
        "institutional_volume": {"relative_volume_1d": 1.4, "persistence_score": 75},
        "participation": {"score": 80},
        "trade_plan": {
            "entry": {"preferred_entry": 100, "zone_low": 99, "zone_high": 101},
            "stop": {"recommended_stop": 95},
            "targets": {"targets": [{"price": 105}, {"price": 110}, {"price": 115}]},
            "structural_reward_risk": 2.0,
            "management_quality": 80,
            "certification": {"status": "PASS", "quality_score": 90},
        },
        "decision_intelligence": {
            "overall_trade_quality": 84,
            "decision_readiness": 81,
            "opportunity_freshness": 95,
            "quality_vector": vector,
            "explainability": {"opportunity_freshness": {"extension_atr": 0.1}},
        },
        "metadata": {"scanner_run_id": "run-1"},
        "state_hash": "point-in-time-state",
    }


def bars(*, ambiguous: bool = False) -> list[dict]:
    start = date(2026, 1, 3)
    result = []
    for index in range(35):
        if index == 0:
            low, high, close = 99.5, 101.0, 100.0
        elif index == 1 and ambiguous:
            low, high, close = 94.0, 106.0, 101.0
        elif index == 1:
            low, high, close = 99.0, 106.0, 105.5
        else:
            low, high, close = 100.0, 104.0, 102.0
        result.append({"date": start + timedelta(days=index), "open": 100, "high": high, "low": low, "close": close})
    return result


def test_daily_barrier_labels_do_not_invent_same_bar_order():
    labeler = BarrierOutcomeLabeler(OutcomeProbabilityPolicy(minimum_training_samples=30))
    ambiguous = labeler.label(
        candidate_id="candidate-1",
        scanner_run_id="run-1",
        candidate_payload=candidate_payload(),
        future_bars=bars(ambiguous=True),
    )
    assert ambiguous.status == "PARTIALLY_AMBIGUOUS"
    assert ambiguous.target_1_before_stop is None
    assert ambiguous.thesis_invalidation is None
    assert "TARGET_1_AND_STOP_SAME_DAILY_BAR" in ambiguous.ambiguous_targets
    resolved = labeler.label(
        candidate_id="candidate-2",
        scanner_run_id="run-1",
        candidate_payload=candidate_payload(),
        future_bars=bars(),
    )
    assert resolved.target_1_before_stop == 1
    assert resolved.thesis_invalidation == 0
    assert resolved.entry_triggered == 1


def test_label_waits_for_full_post_entry_horizon():
    payload = candidate_payload()
    payload["trade_plan"]["entry"] = {
        "preferred_entry": 100,
        "zone_low": 99,
        "zone_high": 101,
    }
    future = bars()[:30]
    for row in future[:4]:
        row.update({"low": 102.0, "high": 104.0, "close": 103.0})
    future[4].update({"low": 99.5, "high": 101.0, "close": 100.0})
    label = BarrierOutcomeLabeler().label(
        candidate_id="candidate-late-entry",
        scanner_run_id="run-1",
        candidate_payload=payload,
        future_bars=future,
    )
    assert label.status == "PENDING_HORIZON"
    assert label.entry_triggered == 1
    assert label.target_1_before_stop is None
    assert label.evidence["available_post_entry_sessions"] == 25


def test_point_in_time_features_are_fixed_and_outcome_free():
    features = PointInTimeFeatureBuilder().build(candidate_payload())
    assert tuple(features) == NUMERIC_FEATURES
    assert all("outcome" not in name and "realized" not in name for name in features)
    assert features["bullish_direction"] == 1.0
    assert features["negative_gamma_regime"] == 1.0


def test_materialization_is_idempotent_and_skips_terminal_observations():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            PriceHistory.__table__,
            StockScannerCandidateModel.__table__,
            OutcomeProbabilityObservationModel.__table__,
        ],
    )
    with Session(engine) as session:
        session.add(
            StockScannerCandidateModel(
                id="candidate-service",
                symbol="TEST",
                scanner_run_id="run-1",
                candidate_id=None,
                snapshot_timestamp="2026-01-02T21:00:00+00:00",
                payload_json=candidate_payload(),
                category="ACCUMULATION_BREAKOUT",
                score=82.0,
            )
        )
        for row in bars():
            session.add(
                PriceHistory(
                    symbol="TEST",
                    date=row["date"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=1_000_000,
                )
            )
        session.commit()
        service = OutcomeProbabilityService(session)
        first = service.materialize_outcomes()
        second = service.materialize_outcomes()
        rows = list(session.scalars(select(OutcomeProbabilityObservationModel)))
        assert first["candidates_processed"] == 1
        assert second["candidates_processed"] == 0
        assert second["candidates_skipped_finalized"] == 1
        assert len(rows) == 1
        assert rows[0].target_1_before_stop == 1


def synthetic_observations(count_dates: int = 200, rows_per_date: int = 10):
    values = []
    index = 0
    for day in range(count_dates):
        as_of_date = date(2025, 1, 1) + timedelta(days=day)
        for within in range(rows_per_date):
            positive = within % 2
            feature_values = {name: 50.0 for name in NUMERIC_FEATURES}
            signal = 90.0 if positive else 10.0
            feature_values["directional_quality"] = signal
            feature_values["trend_quality"] = signal
            feature_values["structure_quality"] = signal
            feature_values["scanner_confidence"] = signal
            values.append(SimpleNamespace(
                observation_id=f"obs-{index}",
                candidate_id=f"candidate-{index}",
                as_of=f"{as_of_date.isoformat()}T20:00:00+00:00",
                horizon_end=(as_of_date + timedelta(days=40)).isoformat(),
                features_json=feature_values,
                target_1_before_stop=positive,
                target_2_before_stop=positive,
                target_3_before_stop=positive,
                profitable_at_horizon=positive,
                thesis_invalidation=1 - positive,
                maximum_favorable_excursion_pct=8.0 if positive else 2.0,
                maximum_adverse_excursion_pct=2.0 if positive else 7.0,
                days_to_target_1=5 if positive else None,
                days_to_stop=4 if not positive else None,
                label_json={"evidence": {"direction": "BULLISH"}},
                lineage_json={"direction": "STRONG_BULLISH"},
                status="REALIZED",
                entry_triggered=1,
            ))
            index += 1
    return values


def test_walk_forward_training_and_shadow_runtime_are_governed():
    policy = OutcomeProbabilityPolicy(
        minimum_training_samples=300,
        minimum_positive_samples=100,
        minimum_negative_samples=100,
        minimum_distinct_as_of_dates=20,
        maximum_test_brier=0.30,
        maximum_test_ece=0.20,
        minimum_test_auc=0.50,
    )
    observations = synthetic_observations()
    artifact, evaluation = GovernedOutcomeModelTrainer(policy).train(observations)
    assert evaluation["partitions"]["same_as_of_date_cross_partition"] is False
    assert evaluation["partitions"]["label_horizon_overlap_cross_partition"] is False
    assert evaluation["partitions"]["purged_for_forward_horizon"] > 0
    assert evaluation["targets"]["target_1_before_stop"]["status"] == "EVALUATED"
    assert evaluation["automatic_activation"] is False
    runtime = OutcomeProbabilityRuntime(
        model_id="model-1",
        model_version="M77-TEST",
        artifact=artifact,
        observations=observations,
        policy=policy,
    )
    assessment = runtime.score(candidate_payload())
    assert assessment.mode == "SHADOW"
    assert assessment.authority_effect is False
    assert assessment.recommended_disposition in {"TRADE", "WATCH", "ABSTAIN"}
    assert assessment.target_1_before_stop is not None
    assert assessment.feature_contributions


def test_m77_is_connected_but_has_no_authority_effect():
    root = Path(__file__).resolve().parents[1]
    orchestration = (root / "src/trading_ai/stock_intelligence/orchestration.py").read_text()
    decision = (root / "src/trading_ai/stock_intelligence/decision_intelligence.py").read_text()
    ingestion = (root / "src/trading_ai/institutional_options/opportunity_ingestion.py").read_text()
    app = (root / "src/trading_ai/production_api/app.py").read_text()
    stock_ui = (root / "ui/workstation/src/StockIntelligenceScannerPage.tsx").read_text()
    io_ui = (root / "ui/workstation/src/InstitutionalOptionsPage.tsx").read_text()
    assert "attach_shadow_assessment" in orchestration
    assert "record_prediction" in orchestration
    assert "outcome_probability" in decision
    assert "M77 shadow probability" in ingestion
    assert "outcome_probability_router" in app
    assert "M77 outcome probability" in stock_ui
    assert "M77 outcome probability · shadow" in io_ui
    assert "cannot change certification, M76 decisions, M64 allocation" in io_ui


def test_shadow_assessment_does_not_change_canonical_candidate_identity():
    profile = StockIntelligenceProfile(
        symbol="TEST",
        snapshot_timestamp="2026-01-02T21:00:00+00:00",
        decision_intelligence=InstitutionalDecisionAssessment().finalize(),
    ).finalize()
    candidate_hash = profile.state_hash
    decision_hash = profile.decision_intelligence.state_hash
    assessment = OutcomeProbabilityService.__new__(OutcomeProbabilityService)
    assessment.features = PointInTimeFeatureBuilder()
    result = assessment.attach_shadow_assessment(profile, None)
    assert result.authority_effect is False
    assert profile.state_hash == candidate_hash
    assert profile.decision_intelligence.state_hash == decision_hash
    assert profile.decision_intelligence.outcome_probability["status"] == "SHADOW_NOT_READY"


def test_readiness_audit_is_success_but_insufficient_training_is_exit_three():
    result = {"status": "INSUFFICIENT_EVIDENCE"}
    assert result_exit_code("audit", result) == 0
    assert result_exit_code("status", result) == 0
    assert result_exit_code("materialize", result) == 0
    assert result_exit_code("train", result) == 3
