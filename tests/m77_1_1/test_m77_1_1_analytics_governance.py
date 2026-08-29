from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _analytics_source():
    return (ROOT / "src/trading_ai/historical_underlying_replay/analytics.py").read_text()


def test_analytics_is_read_only_and_does_not_mutate_champion():
    s = _analytics_source()
    assert "READ_ONLY_POST_REPLAY_ANALYTICS" in s
    assert '"production_authority_effect": False' in s
    assert '"prediction_mutation": False' in s
    assert '"outcome_mutation": False' in s
    for token in (
        "INSERT INTO",
        "UPDATE historical_",
        "DELETE FROM",
        "StockIntelligenceService(",
    ):
        assert token not in s


def test_existing_m77_1_replay_semantics_are_recognized_not_rewritten():
    replay = (ROOT / "src/trading_ai/historical_underlying_replay/service.py").read_text()
    analytics = _analytics_source()
    assert "fixed[str(h)]=round(raw*sign if sign else raw,6)" in replay
    assert "M77.1 persists thesis-aligned returns for directional" in analytics
    assert "M77.1 persists thesis-aligned favorable/adverse excursion" in analytics
    assert "stored replay artifact is not mutated" in analytics


def test_confidence_is_not_misrepresented_as_probability_calibration():
    s = _analytics_source()
    assert "NOT " in s and "treated as a calibrated probability" in s
    assert "Brier/ECE" in s


def test_overlap_and_cluster_governance_present():
    s = _analytics_source()
    assert "_non_overlapping" in s
    assert "symbol_clustered_20d" in s
    assert "date_clustered_60d" in s
    assert "overlap_fraction_pct" in s


def test_neutral_is_evaluated_as_containment_not_directional_hit():
    s = _analytics_source()
    assert "for band in (3.0, 5.0, 8.0):" in s
    assert 'directional = [row for row in rows if row["direction"] in DIRECTIONAL]' in s
    assert 'neutral = [row for row in rows if row["direction"] == "NEUTRAL"]' in s
