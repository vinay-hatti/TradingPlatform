from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    p = ROOT / "scripts/run_m77_5_shadow_policy_certification.py"
    spec = importlib.util.spec_from_file_location("m77_5_runner", p)
    m = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(m)
    return m


def test_runner_is_read_only_research_only():
    s = (ROOT / "scripts/run_m77_5_shadow_policy_certification.py").read_text()
    assert "READ_ONLY_POST_WALK_FORWARD_STABILITY_CERTIFICATION" in s
    assert '"production_authority_effect": False' in s
    assert '"database_writes": False' in s
    assert '"automatic_champion_promotion": False' in s
    assert '"automatic_bearish_inversion": False' in s


def test_does_not_import_database_or_production_services():
    s = (ROOT / "scripts/run_m77_5_shadow_policy_certification.py").read_text()
    assert "SessionLocal" not in s
    assert "sqlalchemy" not in s.lower()
    assert "trading_ai." not in s
    assert "execute(" not in s


def test_only_m77_4_eligible_candidates_are_considered():
    s = (ROOT / "scripts/run_m77_5_shadow_policy_certification.py").read_text()
    assert "research_challenger_eligible" in s
    assert "ONLY_M77_4_RESEARCH_CHALLENGER_ELIGIBLE" in s
    assert '"candidate_search_reopened": False' in s


def test_partial_year_cannot_satisfy_full_year_requirement():
    s = (ROOT / "scripts/run_m77_5_shadow_policy_certification.py").read_text()
    assert "2026 may contribute supporting evidence but never satisfies the full-year holdout requirement." in s
    assert "partial_year_treated_as_full_year" in s


def test_shadow_certification_requires_positive_incremental_edge_and_sample_floor():
    m = _load_module()
    good = {
        "candidate_horizon_id": "x@@20d",
        "candidate_id": "x",
        "dimensions": {"direction": "BULLISH"},
        "horizon": 20,
        "selected_holdout_folds": 2,
        "full_year_holdout_folds": 1,
        "passed_holdout_folds": 2,
        "all_selected_holdouts_passed": True,
        "folds": [
            {
                "validation_year": 2025,
                "period_status": "FULL_YEAR",
                "validation": {
                    "non_overlapping_observations": 120,
                    "thesis_return_avg_pct": 1.2,
                    "directional_hit_rate_pct": 55,
                    "matched_control": {"matched_excess_thesis_return_avg_pct": 0.2},
                    "passed": True,
                },
            },
            {
                "validation_year": 2026,
                "period_status": "PARTIAL_YEAR",
                "validation": {
                    "non_overlapping_observations": 105,
                    "thesis_return_avg_pct": 0.7,
                    "directional_hit_rate_pct": 53,
                    "matched_control": {"matched_excess_thesis_return_avg_pct": 0.1},
                    "passed": True,
                },
            },
        ],
    }
    row = m._candidate_row(good)
    assert row["status"] == "SHADOW_POLICY_CERTIFIED"

    weak = json.loads(json.dumps(good))
    weak["folds"][1]["validation"]["non_overlapping_observations"] = 80
    row = m._candidate_row(weak)
    assert row["status"] == "WALK_FORWARD_SUPPORTED_NOT_SHADOW_CERTIFIED"
    assert "HOLDOUT_SAMPLE_BELOW_100_NON_OVERLAPPING" in row["failure_reasons"]


def test_single_holdout_is_observational_only():
    m = _load_module()
    item = {
        "candidate_horizon_id": "x@@60d",
        "candidate_id": "x",
        "dimensions": {"direction": "BULLISH"},
        "horizon": 60,
        "selected_holdout_folds": 1,
        "full_year_holdout_folds": 1,
        "passed_holdout_folds": 1,
        "all_selected_holdouts_passed": True,
        "folds": [
            {
                "validation_year": 2025,
                "period_status": "FULL_YEAR",
                "validation": {
                    "non_overlapping_observations": 1000,
                    "thesis_return_avg_pct": 2.0,
                    "directional_hit_rate_pct": 60,
                    "matched_control": {"matched_excess_thesis_return_avg_pct": 0.3},
                    "passed": True,
                },
            }
        ],
    }
    assert m._candidate_row(item)["status"] == "OBSERVATIONAL_WALK_FORWARD_SUPPORT"
