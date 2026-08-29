from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
scanner = (root / "src/trading_ai/daily/scanner.py").read_text()
cli = (root / "scripts/run_daily_scan.py").read_text()
recommender = (
    root / "src/trading_ai/daily/recommender.py"
).read_text()

checks = {
    "concrete expiry assignment":
        "expiry=expiry_selection.expiration_iso" in scanner,
    "expiry selector import":
        "StandardFridayExpirySelector" in scanner,
    "no DTE proxy in scanner":
        "DTE_PROXY" not in scanner,
    "CLI expiration output":
        "Expiration" in cli,
    "minimum premium guard":
        "minimum_option_price" in recommender,
    "maximum contract cap":
        "maximum_contracts" in recommender,
}

failed = False
for name, passed in checks.items():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    failed = failed or not passed

raise SystemExit(1 if failed else 0)
