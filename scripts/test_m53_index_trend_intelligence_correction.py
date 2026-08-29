from pathlib import Path

root = Path(__file__).resolve().parents[1]
base_service = (root / "src/trading_ai/trend_intelligence/service.py").read_text()
institutional_service = (root / "src/trading_ai/trend_intelligence/institutional_service.py").read_text()
institutional_runner = (root / "scripts/run_institutional_trend_intelligence.py").read_text()

for symbol in ("SPX", "NDX", "RUT"):
    assert f'"{symbol}"' in base_service
    assert f'"{symbol}"' in institutional_service
    assert symbol in institutional_runner

assert '"SPX": "SPY"' in institutional_service
assert '"NDX": "QQQ"' in institutional_service
assert '"RUT": "IWM"' in institutional_service
assert 'INDEX_VOLUME_PROXY' in institutional_service
assert 'dropna(subset=["date", "close"])' in institutional_service
print("Milestone 53 index trend intelligence correction assertions passed.")
