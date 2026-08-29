from pathlib import Path
import subprocess, sys, json

MANDATORY=[
"scripts/test_portfolio_optimization.py",
"scripts/test_portfolio_optimization_integration.py",
"scripts/test_portfolio_optimization_reporting.py",
"scripts/test_portfolio_optimization_frontier.py",
"scripts/test_portfolio_optimization_frontier_reporting.py",
"scripts/test_portfolio_optimization_recommendation.py",
]
OPTIONAL=["scripts/test_phase4_regression.py","scripts/test_institutional_decision_engine.py"]

def run(path):
    result=subprocess.run([sys.executable,path])
    if result.returncode: raise SystemExit(result.returncode)

def main():
    result=subprocess.run([sys.executable,"-m","compileall","-q","src","scripts"]); assert result.returncode==0
    for path in MANDATORY:
        if not Path(path).exists(): raise AssertionError(f"Missing mandatory regression test: {path}")
        run(path)
    for path in OPTIONAL:
        if Path(path).exists(): run(path)
    print("Milestone 29 Phase 5 regression assertions passed.")
    print("Milestone 29 Phase 5: COMPLETE")

if __name__ == "__main__": main()
