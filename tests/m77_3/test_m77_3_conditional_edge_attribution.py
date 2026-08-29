from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_m77_3_is_read_only_and_no_production_promotion():
    source = (ROOT / "src/trading_ai/historical_underlying_replay/attribution.py").read_text()
    upper = source.upper()
    assert '"production_authority_effect": False' in source
    assert '"production_model_mutation": False' in source
    assert '"automatic_threshold_change": False' in source
    assert '"automatic_bearish_inversion": False' in source
    assert '"automatic_champion_promotion": False' in source
    for token in ("INSERT INTO", "UPDATE ", "DELETE FROM", ".COMMIT("):
        assert token not in upper


def test_regime_authority_is_point_in_time_price_history_only():
    source = (ROOT / "src/trading_ai/historical_underlying_replay/regime.py").read_text()
    assert "WHERE date <= :end" in source
    assert "price_history" in source
    assert "current_market_state" not in source
    assert "FROM option_" not in source
    assert "JOIN option_" not in source
    assert "FROM dealer" not in source.lower()
    assert "JOIN dealer" not in source.lower()


def test_candidate_registry_requires_independent_and_cross_year_evidence():
    source = (ROOT / "src/trading_ai/historical_underlying_replay/attribution.py").read_text()
    assert "MIN_NONOVERLAP_20" in source
    assert "MIN_NONOVERLAP_60" in source
    assert "positive_symbol_rate_pct" in source
    assert "worst_year_thesis_return_pct" in source
    assert "matched_excess_thesis_return_avg_pct" in source
    assert "MULTIYEAR_SUPPORTED" in source


def test_bearish_failure_is_attributed_not_auto_inverted():
    source = (ROOT / "src/trading_ai/historical_underlying_replay/attribution.py").read_text()
    assert "RELATIVE_UNDERPERFORMANCE_ONLY" in source
    assert "NO_ABSOLUTE_OR_RELATIVE_BEARISH_EDGE" in source
    assert '"automatic_inversion_allowed": False' in source


def test_matched_control_is_leave_one_out_same_date_regime_score_band():
    source = (ROOT / "src/trading_ai/historical_underlying_replay/attribution.py").read_text()
    assert '(row["as_of"], row["historical_regime"], row["score_band"])' in source
    assert "leave-one-out same replay date + historical regime + overall-score band" in source
