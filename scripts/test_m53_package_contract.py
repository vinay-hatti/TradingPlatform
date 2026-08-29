from pathlib import Path

REQUIRED=[
"src/trading_ai/market_overview/contracts.py",
"src/trading_ai/market_overview/service.py",
"src/trading_ai/market_overview/router.py",
"ui/workstation/src/pages.tsx",
"ui/workstation/src/styles.css",
"scripts/test_m53_trend_intelligence_aggregation.py",
"scripts/test_m53_ui_contract.py",
]
def main():
    missing=[p for p in REQUIRED if not Path(p).exists()]
    assert not missing, f"Missing Milestone 53 files: {missing}"
    print("All Milestone 53 package contract assertions passed.")
if __name__=="__main__": main()
