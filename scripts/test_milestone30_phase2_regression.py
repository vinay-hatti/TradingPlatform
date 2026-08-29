import argparse, subprocess, sys
from pathlib import Path
TESTS=(
"scripts/test_realtime_market_data_foundation.py",
"scripts/test_realtime_provider_lifecycle.py",
"scripts/test_paper_streaming_pipeline.py",
"scripts/test_market_hours_feed_recovery.py",
"scripts/test_market_data_reconciliation.py",
"scripts/test_market_data_quality_reporting.py",
)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--allow-missing",action="store_true"); args=parser.parse_args()
    missing=[]; failed=[]
    for script in TESTS:
        if not Path(script).exists():
            missing.append(script); print(f"[MISSING] {script}"); continue
        print(f"[RUN] {script}")
        r=subprocess.run([sys.executable,script])
        if r.returncode: failed.append((script,r.returncode))
    if missing and not args.allow_missing: raise AssertionError("Missing tests: "+", ".join(missing))
    if failed: raise AssertionError("Failed tests: "+", ".join(f"{s}({c})" for s,c in failed))
    print("All available Milestone 30 Phase 2 regression assertions passed.")
if __name__=="__main__": main()
