import pandas as pd

from trading_ai.indicators.feature_engine import FeatureEngine
from trading_ai.options.scoring import OptionsScoringEngine
from trading_ai.feature_store.pipeline import FeaturePipeline


def test_pipeline():
    dates = pd.date_range("2026-01-01", periods=180, freq="D")
    close = pd.Series(range(100, 280), dtype=float)
    frame = pd.DataFrame({
        "date": dates,
        "open": close - 0.5,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": 1_000_000.0,
    })
    result = FeaturePipeline(FeatureEngine(), OptionsScoringEngine()).run(frame)
    assert "ema20" in result.columns
