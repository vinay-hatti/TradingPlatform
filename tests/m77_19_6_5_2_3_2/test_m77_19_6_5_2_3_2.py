import datetime as dt
import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_2_3_2_native_comparator_monthly_session_cutoff_forensics.py"
)

spec = importlib.util.spec_from_file_location(
    "m77_5232",
    P,
)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


class Native:
    @staticmethod
    def compare_profile(profile, frozen):
        return {
            "stored": {
                "direction": frozen["direction"],
                "overall_score": frozen["overall_score"],
                "confidence": frozen["confidence"],
                "state_hash": frozen.get("state_hash"),
            },
            "isolated": {
                "direction": profile["direction"],
                "overall_score": profile["score"],
                "confidence": profile["confidence"],
                "state_hash": profile.get("state_hash"),
            },
            "direction_match": (
                profile["direction"]
                == frozen["direction"]
            ),
            "score_abs_error": abs(
                profile["score"]
                - frozen["overall_score"]
            ),
            "confidence_abs_error": abs(
                profile["confidence"]
                - frozen["confidence"]
            ),
            "state_hash_match": False,
        }


def test_native_comparator_extracts_score():
    result = m.extract_native_comparison(
        Native(),
        {
            "direction": "BULLISH",
            "score": 10.2,
            "confidence": 85.38,
        },
        {
            "direction": "BULLISH",
            "overall_score": 10.0,
            "confidence": 85.62,
        },
    )

    assert round(
        result["score_signed_error"],
        2,
    ) == 0.2

    assert round(
        result["confidence_signed_error"],
        2,
    ) == -0.24


def test_exact_match_is_strict():
    result = {
        "direction_match": True,
        "score_abs_error": 0.0,
        "confidence_abs_error": 0.0,
    }

    assert m.exact_match(result)

    result["score_abs_error"] = 1e-8

    assert not m.exact_match(result)


def test_candidate_sessions():
    sessions = [
        dt.date(2022, 10, day)
        for day in (
            24,
            25,
            26,
            27,
            28,
            31,
        )
    ]

    candidates = m.candidate_sessions(
        dt.date(2022, 10, 31),
        sessions,
    )

    assert candidates[0] == dt.date(
        2022,
        10,
        31,
    )

    assert candidates[1] == dt.date(
        2022,
        10,
        28,
    )


def test_tolerance_unchanged():
    assert m.NUMERIC_TOLERANCE == 1e-9


def test_backtrack_bound():
    assert m.MAX_SESSION_BACKTRACK == 8


def test_no_profile_field_discovery():
    text = P.read_text()

    assert "def certify_adapter(" not in text
    assert "def terminal_candidates(" not in text
    assert "def flatten(" not in text
