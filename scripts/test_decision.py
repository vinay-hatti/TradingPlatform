import yfinance as yf

from trading_ai.decision.engine import DecisionEngine
from trading_ai.feature_store.pipeline import FeaturePipeline


df = yf.download("AAPL", period="6mo", auto_adjust=True)

# Normalize columns if MultiIndex is returned
if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
    df.columns = df.columns.get_level_values(0)

df.columns = [str(c).lower() for c in df.columns]

pipeline = FeaturePipeline()

features = pipeline.run(df)

decision = DecisionEngine().decide(
    "AAPL",
    features.iloc[-1],
)

print(decision)
