import ast
from pathlib import Path
MODULES=(
"src/trading_ai/market/realtime_market_data_policy.py",
"src/trading_ai/market/realtime_market_data_profile.py",
"src/trading_ai/market/realtime_market_data_normalizer.py",
"src/trading_ai/market/realtime_market_data_quality_engine.py",
"src/trading_ai/market/realtime_market_data_service.py",
"src/trading_ai/market/realtime_provider_adapter.py",
"src/trading_ai/market/realtime_subscription_registry.py",
"src/trading_ai/market/realtime_connection_lifecycle.py",
"src/trading_ai/market/realtime_provider_service.py",
"src/trading_ai/market/paper_streaming_adapter.py",
"src/trading_ai/market/realtime_event_dispatcher.py",
"src/trading_ai/market/realtime_market_data_pipeline.py",
"src/trading_ai/market/market_hours_service.py",
"src/trading_ai/market/stale_feed_monitor.py",
"src/trading_ai/market/reconnection_governance.py",
"src/trading_ai/market/feed_recovery_service.py",
"src/trading_ai/market/market_data_reconciliation_engine.py",
"src/trading_ai/market/market_data_quality_reporting.py",
)
COMMANDS=(
"realtime-market-data-test","realtime-provider-test","paper-streaming-test",
"market-hours-feed-test","market-data-reconciliation-test",
"market-data-quality-report","milestone30-phase2-regression-test",
"milestone30-phase2-closure-test",
)
def main():
    missing=[p for p in MODULES if not Path(p).exists()]
    assert not missing, "Missing modules: "+", ".join(missing)
    source=Path("src/trading_ai/__main__.py").read_text(); ast.parse(source)
    for command in COMMANDS: assert command in source, f"Missing CLI command: {command}"
    report=Path("src/trading_ai/market/market_data_quality_reporting.py").read_text()
    for heading in ("Normalized Market Data Pipeline","Feed Health and Recovery","Live/Historical Reconciliation","Diagnostics"):
        assert heading in report
    print("All Milestone 30 Phase 2 closure assertions passed.")
if __name__=="__main__": main()
