from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/"scripts/run_m77_12_cadence_role_incremental_utility.py"

def s():return RUN.read_text()

def test_frozen_cohorts_only():
    x=s();assert '"frozen_baseline_cohorts_only":True' in x;assert '"neighboring_cohort_search":False' in x

def test_predeclared_roles():
    x=s();assert '("CONFIRMING","NEUTRAL","CONFLICTING")' in x;assert "NOT_APPLICABLE_NEUTRAL_BASELINE" in x

def test_backward_only_binding():
    x=s();assert "bisect.bisect_right" in x;assert '"future_leakage_prohibited":True' in x

def test_nested_incremental_comparison():
    x=s();assert "incremental_vs_same_frozen_baseline_pct" in x;assert '"comparison":"role subset versus same frozen certified baseline, same year/horizon"' in x

def test_neutral_monthly_not_misrepresented():
    x=s();assert "monthly_neutral_excluded_from_directional_overlay" in x;assert "excluded from directional CONFIRMING/CONFLICTING" in x

def test_governance():
    x=s();assert '"database_writes":False' in x;assert '"production_authority_effect":False' in x;assert '"automatic_shadow_activation":False' in x;assert '"automatic_champion_promotion":False' in x

def test_no_replay_mutation():
    assert ".run_baseline(" not in s()
