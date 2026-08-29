from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / "src/trading_ai/inflection_intelligence/engine.py"
spec = importlib.util.spec_from_file_location("m68_2_engine", ENGINE_PATH)
engine_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = engine_module
spec.loader.exec_module(engine_module)
Bar = engine_module.Bar
InstitutionalInflectionEngine = engine_module.InstitutionalInflectionEngine


def trend_bars(direction: int) -> list[Bar]:
    values = [100.0 + direction * index * 0.75 for index in range(40)]
    return [
        Bar(
            close=value,
            high=value + 0.45,
            low=value - 0.45,
            volume=1_000_000 + index * 2_000,
            as_of=f"2026-07-{index + 1:02d}",
        )
        for index, value in enumerate(values)
    ]


def exact_inputs() -> tuple[dict, dict]:
    return (
        {"implied_volatility": 0.28, "spread_pct": 3.0},
        {
            "bull_probability": 0.70,
            "bear_probability": 0.30,
            "confidence_score": 90.0,
            "quote_coverage_pct": 99.0,
        },
    )


def test_direction_is_signed_and_symmetric() -> None:
    candidate, dealer = exact_inputs()
    engine = InstitutionalInflectionEngine()
    bullish = engine.evaluate(
        "UP", trend_bars(1), candidate_payload=candidate,
        dealer_payload=dealer, breadth_score=65,
        build_mode="OPTIONS_ENRICHMENT",
    )
    bearish_dealer = {**dealer, "bull_probability": 0.30, "bear_probability": 0.70}
    bearish = engine.evaluate(
        "DOWN", trend_bars(-1), candidate_payload=candidate,
        dealer_payload=bearish_dealer, breadth_score=35,
        build_mode="OPTIONS_ENRICHMENT",
    )
    assert bullish["direction"] == "BULLISH"
    assert bullish["directional_score"] > 0
    assert bearish["direction"] == "BEARISH"
    assert bearish["directional_score"] < 0
    assert abs(abs(bullish["directional_score"]) - abs(bearish["directional_score"])) < 12


def test_flat_market_is_neutral_and_abstains() -> None:
    bars = [
        Bar(100.0, 100.2, 99.8, 1_000_000, f"2026-06-{index + 1:02d}")
        for index in range(30)
    ]
    candidate, _ = exact_inputs()
    result = InstitutionalInflectionEngine().evaluate(
        "FLAT", bars, candidate_payload=candidate,
        dealer_payload={"bull_probability": 0.5, "bear_probability": 0.5},
        breadth_score=50, build_mode="OPTIONS_ENRICHMENT",
    )
    assert result["direction"] == "NEUTRAL"
    assert abs(result["directional_score"]) < 15
    assert result["disposition"] == "ABSTAIN"


def test_missing_options_inputs_fail_closed() -> None:
    result = InstitutionalInflectionEngine().evaluate(
        "MISSING", trend_bars(1), candidate_payload={}, dealer_payload={},
        breadth_score=60, build_mode="OPTIONS_ENRICHMENT",
    )
    assert result["disposition"] == "ABSTAIN"
    assert "dealer" in result["missing_inputs"]
    assert "implied_volatility" in result["missing_inputs"]
    assert "option_liquidity" in result["missing_inputs"]


def test_steady_trend_is_not_mislabeled_reversal() -> None:
    candidate, dealer = exact_inputs()
    result = InstitutionalInflectionEngine().evaluate(
        "STEADY", trend_bars(1), candidate_payload=candidate,
        dealer_payload=dealer, breadth_score=65,
        build_mode="OPTIONS_ENRICHMENT",
    )
    assert result["transition_state"] != "REVERSAL_SETUP"
    assert result["diagnostics"]["material_acceleration"] is False


def test_deterministic_fingerprints() -> None:
    candidate, dealer = exact_inputs()
    engine = InstitutionalInflectionEngine()
    first = engine.evaluate(
        "HASH", trend_bars(1), candidate_payload=candidate,
        dealer_payload=dealer, breadth_score=65,
        build_mode="OPTIONS_ENRICHMENT",
    )
    second = engine.evaluate(
        "HASH", trend_bars(1), candidate_payload=candidate,
        dealer_payload=dealer, breadth_score=65,
        build_mode="OPTIONS_ENRICHMENT",
    )
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["semantic_state_hash"] == second["semantic_state_hash"]
    assert first["state_hash"] == second["state_hash"]


def test_dual_path_ownership_and_exact_downstream_lineage_are_present() -> None:
    ingestion = (ROOT / "scripts/ingestion_split_common.py").read_text()
    analytics = (ROOT / "src/trading_ai/analytics_dashboard/service.py").read_text()
    valuation = (
        ROOT / "src/trading_ai/option_valuation_intelligence/service.py"
    ).read_text()
    position = (
        ROOT / "src/trading_ai/autonomous_position_management/service.py"
    ).read_text()
    assert 'scope == "options"' in ingestion
    assert "latest_materialized_stock_publication()" in ingestion
    assert "authority_owner\": \"UNDERLYING_INGESTION" in ingestion
    assert "== publication.source_run_id" in analytics
    assert "inf_pub.source_run_id == opp.stock_scanner_run_id" in valuation
    assert "InflectionSnapshotModel.timeframe == '1d'" in valuation
    assert "inf.get('coverage_status')=='CURRENT_EXACT'" in position
    assert "SNAPSHOT_RETENTION_RUNS = 40" in (
        ROOT / "src/trading_ai/inflection_intelligence/service.py"
    ).read_text()
    service = (
        ROOT / "src/trading_ai/inflection_intelligence/service.py"
    ).read_text()
    assert service.index("previous_semantic = previous.semantic_state_hash") < service.index(
        'setattr(model, field, result[field])'
    )


def test_schema_migration_follows_current_head() -> None:
    migration = (
        ROOT / "migrations/versions/m68_002_governed_directional_inflection.py"
    ).read_text()
    assert 'revision = "m68_002"' in migration
    assert 'down_revision = "m71_004"' in migration
    assert "uq_m68_timeline_event_fingerprint" in migration
    assert "authority_input_fingerprint" in migration
