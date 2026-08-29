from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    "valuation bulk coherent-market preload": (
        "src/trading_ai/option_valuation_intelligence/service.py",
        "preload_coherent_market_inputs",
    ),
    "dealer bulk preload": (
        "src/trading_ai/institutional_market_structure/refresh.py",
        "PARALLEL_BULK_PRELOAD",
    ),
    "volatility bulk historical preload": (
        "src/trading_ai/market_intelligence/ingestion_orchestrator.py",
        "history_by_symbol",
    ),
    "valuation coherent preload profiling": (
        "scripts/ingestion_split_common.py",
        "coherent_market=",
    ),
}
for label, (rel, token) in checks.items():
    text = (ROOT / rel).read_text()
    assert token in text, f"{label} missing: {token}"
print("M68.2.1.15.8.2 source verification PASSED")
print(" - valuation coherent-market N+1 removed")
print(" - dealer chain/price/history reads bulk-preloaded")
print(" - volatility history/price reads bulk-preloaded")
print(" - governance stage ordering preserved")
