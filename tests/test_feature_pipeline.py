import yfinance as yf

from trading_ai.indicators.feature_engine import FeatureEngine
from trading_ai.options.scoring import OptionsScoringEngine
from trading_ai.feature_store.pipeline import FeaturePipeline


def test_pipeline():

    df = yf.download("AAPL", period="6mo")

    if hasattr(df.columns, "droplevel"):
        df.columns = df.columns.droplevel(-1)

    df.columns = [c.lower() for c in df.columns]

    pipeline = FeaturePipeline(
        FeatureEngine(),
        OptionsScoringEngine(),
    )

    df = pipeline.run(df)

    assert "ema20" in df.columns
