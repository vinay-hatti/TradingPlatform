from pathlib import Path
import py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_14_3_prospective_lunar_volatility_shadow.py"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_frozen_hypothesis():
    x=R.read_text()
    assert 'TARGET = "NDX"' in x
    assert 'HORIZON = 10' in x
    assert 'HYPOTHESIS = "FIRST_QUARTER_WINDOW"' in x
    assert 'OUTCOME = "ABSOLUTE_RETURN"' in x
    assert 'EXPECTED_DIRECTION = "SUPPRESSED_10D_ABSOLUTE_MOVE"' in x

def test_episode_cluster():
    x=R.read_text()
    assert "episode_id_for" in x
    assert "earliest captured session in cluster" in x

def test_prospective_only():
    x=R.read_text()
    assert "entry_close" in x
    assert "i + HORIZON" in x
    assert "MATURED" in x

def test_governance():
    x=R.read_text()
    assert '"research_only": True' in x
    assert '"automatic_promotion": False' in x
    assert '"production_authority_effect": False' in x
    assert '"production_model_or_weight_change": False' in x
    assert '"neighboring_search": False' in x

def test_minimum_episodes():
    x=R.read_text()
    assert "MIN_COMPLETED_EPISODES_FOR_REVIEW = 12" in x
