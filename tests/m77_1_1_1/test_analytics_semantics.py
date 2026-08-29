from trading_ai.historical_underlying_replay.analytics import (
    _raw_excursions_from_stored,
    _raw_return_from_stored,
    _thesis_return_from_stored,
)


def test_bearish_stored_return_is_already_thesis_aligned():
    # M77.1 stores raw*sign. A -8% raw underlying move under a bearish thesis
    # is therefore stored as +8%, not -8%.
    assert _thesis_return_from_stored("BEARISH", 8.0) == 8.0
    assert _raw_return_from_stored("BEARISH", 8.0) == -8.0


def test_bearish_failed_thesis_is_not_double_inverted():
    # If the underlying rose 8% after a bearish prediction, M77.1 stores -8%.
    assert _thesis_return_from_stored("STRONG_BEARISH", -8.0) == -8.0
    assert _raw_return_from_stored("STRONG_BEARISH", -8.0) == 8.0


def test_bullish_semantics_are_identity():
    assert _thesis_return_from_stored("BULLISH", 6.5) == 6.5
    assert _raw_return_from_stored("BULLISH", 6.5) == 6.5


def test_neutral_has_raw_but_no_directional_thesis_return():
    assert _raw_return_from_stored("NEUTRAL", 4.0) == 4.0
    assert _thesis_return_from_stored("NEUTRAL", 4.0) is None


def test_bearish_excursion_reconstruction():
    # Stored bearish thesis MFE=+12 (downside favorable), MAE=-5 (upside adverse).
    raw_mfe, raw_mae = _raw_excursions_from_stored("BEARISH", 12.0, -5.0)
    assert raw_mfe == 5.0
    assert raw_mae == -12.0
