import yfinance as yf
import pandas as pd

from trading_ai.feature_store.pipeline import FeaturePipeline
from trading_ai.indicators.feature_engine import FeatureEngine
from trading_ai.options.scoring import OptionsScoringEngine

df = yf.download("AAPL", period="6mo", interval="1d")

# -----------------------------
# FIX: flatten multi-index cols
# -----------------------------
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# normalize names
df.columns = [str(c).lower() for c in df.columns]

#pipeline = FeaturePipeline()
pipeline = FeaturePipeline(
    FeatureEngine(),
    OptionsScoringEngine(),
)

df = pipeline.run(df)

print(df.tail())
print(df[["call_score", "put_score", "signal"]].tail())
print(df[["trade", "strike", "delta"]].tail())
