from pathlib import Path
import subprocess
import sys

TESTS = (
    "test_observability_foundation.py",
    "test_observability_instrumentation_integration.py",
    "test_observability_metrics_exporters.py",
    "test_observability_governance.py",
    "test_observability_reporting_dashboard.py",
)

def main():
    scripts = Path(__file__).resolve().parent
    for name in TESTS:
        path = scripts / name
        assert path.exists(), name
        subprocess.run([sys.executable, str(path)], check=True)
    print("All available Milestone 30 Phase 9 regression assertions passed.")

if __name__ == "__main__":
    main()
