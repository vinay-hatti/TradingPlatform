from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "scripts/run_cyclical_seasonality_research_audit.py"


def load_module():
    spec = spec_from_file_location("cyclical_audit", RUN)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_research_only():
    s = RUN.read_text()
    assert '"database_writes": False' in s
    assert '"production_authority_effect": False' in s
    assert '"production_model_mutation": False' in s
    assert '"automatic_champion_promotion": False' in s


def test_sessionlocal_select_only():
    s = RUN.read_text()
    assert "from trading_ai.database.session import SessionLocal" in s
    assert "DATABASE_URL" not in s
    assert "INSERT INTO" not in s.upper()
    assert "UPDATE " not in s.upper()
    assert "DELETE FROM" not in s.upper()


def test_directional_alignment_contract():
    m = load_module()
    assert m.align_return("BULLISH", 3.5) == 3.5
    assert m.align_return("STRONG_BULLISH", -2.0) == -2.0
    assert m.align_return("BEARISH", -3.5) == 3.5
    assert m.align_return("STRONG_BEARISH", 2.0) == -2.0


def test_raw_and_thesis_fields_are_separate():
    s = RUN.read_text()
    assert '"raw_underlying_return_avg_pct"' in s
    assert '"non_overlapping_raw_underlying_return_avg_pct"' in s
    assert '"non_overlapping_thesis_return_avg_pct"' in s
    assert '"non_overlapping_directional_hit_rate_pct"' in s


def test_weekday_is_diagnostic_only():
    s = RUN.read_text()
    assert '"weekday_eligible": factor != "weekday"' in s
    assert "weekday is diagnostic-only" in s


def test_alias_detection_blocks_promotion():
    s = RUN.read_text()
    assert "detect_factor_aliases" in s
    assert '"independent_factor_state": not factor_state_aliased' in s
    assert "both aliased" in s


def test_fdr_and_effect_floor_present():
    s = RUN.read_text()
    assert "BENJAMINI_HOCHBERG" in s
    assert "bh_qvalues" in s
    assert "MIN_MATCHED_EXCESS_BY_HORIZON" in s
    assert '"matched_excess_effect_floor"' in s
    assert '"fdr_q_le_0_10"' in s


def test_walk_forward_required():
    s = RUN.read_text()
    assert '"walk_forward_required_before_any_shadow_or_production_use": True' in s
    assert "HYPOTHESIS_WORTH_WALK_FORWARD" in s
