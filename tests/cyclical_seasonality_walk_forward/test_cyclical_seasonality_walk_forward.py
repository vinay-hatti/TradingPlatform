from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "scripts/run_cyclical_seasonality_walk_forward.py"


def test_research_only_governance():
    s = RUN.read_text()
    assert '"database_writes": False' in s
    assert '"production_authority_effect": False' in s
    assert '"production_model_mutation": False' in s
    assert '"automatic_shadow_activation": False' in s
    assert '"automatic_champion_promotion": False' in s


def test_expanding_window_training_only_selection():
    s = RUN.read_text()
    assert "training_eligible" in s
    assert '"expanding_window": True' in s
    assert '"training_only_selection": True' in s
    assert '"full_sample_1_1_research_screen_used_for_holdout_selection": False' in s


def test_weekday_and_aliases_excluded():
    s = RUN.read_text()
    assert 'e["factor"] != "weekday"' in s
    assert '(e["factor"], e["state"]) not in aliased' in s
    assert '"exact_alias_states_excluded": True' in s


def test_partial_2026_not_full_year_credit():
    s = RUN.read_text()
    assert '{"holdout_year": 2026, "credit": "PARTIAL_YEAR"}' in s
    assert '"partial_year_2026_is_supporting_only": True' in s


def test_holdout_pass_requires_sample_return_and_hit():
    s = RUN.read_text()
    assert "HOLDOUT_NONOVERLAP_SAMPLE_BELOW_100" in s
    assert "HOLDOUT_THESIS_RETURN_NONPOSITIVE" in s
    assert "HOLDOUT_DIRECTIONAL_HIT_BELOW_50" in s


def test_full_sample_matched_excess_cannot_drive_holdout():
    s = RUN.read_text()
    assert "full_sample_matched_excess_reference_pct" in s
    assert "cannot rescue or determine a holdout pass" in s


def test_next_gate_is_stricter_matched_control_hardening():
    s = RUN.read_text()
    assert "FOLD_NATIVE_MATCHED_CONTROL_HARDENING_AND_SHADOW_CERTIFICATION" in s
