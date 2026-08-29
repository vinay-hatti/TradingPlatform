import importlib.util, sys
from pathlib import Path
from unittest.mock import patch
def load_cli():
    p=Path("src/trading_ai/milestone30_phase2_step5___main__.py")
    spec=importlib.util.spec_from_file_location("m30p2cli",p); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
def check(module,command,script):
    with patch.object(module,"run_script") as runner:
        with patch.object(sys,"argv",["trading_ai",command,"--x","1"]): module.main()
        runner.assert_called_once_with(script,["--x","1"])
def main():
    m=load_cli()
    mapping={
    "realtime-market-data-test":"scripts/test_realtime_market_data_foundation.py",
    "realtime-provider-test":"scripts/test_realtime_provider_lifecycle.py",
    "paper-streaming-test":"scripts/test_paper_streaming_pipeline.py",
    "market-hours-feed-test":"scripts/test_market_hours_feed_recovery.py",
    "market-data-reconciliation-test":"scripts/test_market_data_reconciliation.py",
    "market-data-quality-report":"scripts/build_market_data_quality_report.py",
    "milestone30-phase2-regression-test":"scripts/test_milestone30_phase2_regression.py",
    "milestone30-phase2-closure-test":"scripts/test_milestone30_phase2_closure.py"}
    for c,s in mapping.items(): check(m,c,s)
    print("All Milestone 30 Phase 2 CLI assertions passed.")
if __name__=="__main__": main()
