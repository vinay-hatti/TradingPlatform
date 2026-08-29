import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_2_4_monthly_feature_confidence_component_forensics.py"
)

spec = importlib.util.spec_from_file_location(
    "m77_524",
    P,
)

m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_numeric():
    assert m.numeric(1) == 1.0
    assert m.numeric(1.2) == 1.2
    assert m.numeric(True) is None


def test_flatten():
    value = {
        "scores": {
            "overall": 50.0
        },
        "states": [
            {
                "score": 1.0
            }
        ],
    }

    flat = m.flatten(value)

    assert flat["scores.overall"] == 50.0
    assert flat["states.0.score"] == 1.0


def test_compare_shared_numeric_path():
    rows = m.compare_shared_paths(
        {
            "confidence": 85.38
        },
        {
            "confidence": 85.62
        },
    )

    assert len(rows) == 1
    assert round(
        rows[0]["signed_error"],
        2,
    ) == -0.24


def test_find_value_paths():
    flat = {
        "scores.overall": 55.2,
        "other": 55.2,
        "confidence": 80.0,
    }

    paths = m.find_value_paths(
        flat,
        55.2,
    )

    assert paths == [
        "other",
        "scores.overall",
    ]


def test_tolerance_unchanged():
    assert m.NUMERIC_TOLERANCE == 1e-9


def test_expected_prior_report_sha_pinned():
    assert (
        m.EXPECTED_5232_REPORT_SHA256
        == "3f43cc0ae88dad4f322240e419a1f3c090e178a6d835256bdee3b9437246a58b"
    )


def test_no_production_certification():
    text = P.read_text()

    assert (
        '"controlled_exact_input_parity_certified": False'
        in text
    )

    assert (
        '"full_23_year_reconstruction_authorized": False'
        in text
    )

    assert (
        '"production_authority_effect": False'
        in text
    )
