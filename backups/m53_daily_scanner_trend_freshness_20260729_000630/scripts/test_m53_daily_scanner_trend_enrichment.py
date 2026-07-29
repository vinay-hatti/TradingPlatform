from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
scanner = (ROOT / "src/trading_ai/daily/scanner.py").read_text()
models = (ROOT / "src/trading_ai/daily/models.py").read_text()
trade = (ROOT / "src/trading_ai/daily/trade_candidate.py").read_text()
recommender = (ROOT / "src/trading_ai/daily/recommender.py").read_text()
reporter = (ROOT / "src/trading_ai/daily/reporter.py").read_text()
ui = (ROOT / "ui/workstation/src/pages.tsx").read_text()

for token in (
    "TrendForecastRepository", "InstitutionalTrendRepository",
    "_trend_forecast_context", "_institutional_trend_context",
    "**forecast_context", "**institutional_context",
    "forecast_adjustment", "institutional_adjustment",
):
    assert token in scanner, token

for content in (models, trade, recommender, reporter):
    for token in (
        "forecast_context_status", "forecast_direction", "forecast_confidence_score",
        "institutional_context_status", "participation_score", "participation_state",
        "institutional_conviction_score", "institutional_score_adjustment",
    ):
        assert token in content, (token, content[:40])

assert "trade.forecast_context_status" in ui
assert "trade.institutional_context_status" in ui
assert "Institutional {numeric(trade.institutional_score_adjustment)" in ui
print("Milestone 53 Daily Scanner trend enrichment contract passed.")
