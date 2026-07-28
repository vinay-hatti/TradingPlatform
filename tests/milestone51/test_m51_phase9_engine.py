from trading_ai.paper_trading.operational_readiness import (
    OperationalReadinessEngine,
    ReadinessControl,
)


def test_operationally_ready_when_all_controls_pass():
    controls = [
        ReadinessControl(
            control_id="A", category="TEST", title="A",
            status="PASS", score=100, weight=1
        )
    ]
    engine = OperationalReadinessEngine()
    categories = engine.category_scores(controls)
    score = engine.overall_score(controls)
    status, _ = engine.final_status(controls, categories, score)
    assert status == "PHASE9_OPERATIONALLY_READY"


def test_failed_control_blocks_acceptance():
    controls = [
        ReadinessControl(
            control_id="A", category="TEST", title="A",
            status="FAIL", score=0, weight=1, errors=("FAILED",)
        )
    ]
    engine = OperationalReadinessEngine()
    categories = engine.category_scores(controls)
    score = engine.overall_score(controls)
    status, _ = engine.final_status(controls, categories, score)
    assert status == "PHASE9_NOT_READY_FOR_PRODUCTION_ACCEPTANCE"
