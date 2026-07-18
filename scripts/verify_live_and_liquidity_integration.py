from pathlib import Path

root = Path(__file__).resolve().parents[1]

checks = {
    "live selector":
        "LiveOptionContractSelector",
    "option data mode":
        "option_data_mode",
    "contract ticker propagation":
        "contract_ticker",
    "liquidity score capture":
        "liquidity_score",
    "OI score capture":
        "open_interest_selection_score",
    "volume score capture":
        "volume_selection_score",
}

scanner = (
    root / "src/trading_ai/daily/scanner.py"
).read_text(encoding="utf-8")

failed = False
for name, token in checks.items():
    passed = token in scanner
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    failed = failed or not passed

selector = (
    root / "src/trading_ai/options/live_contract_selector.py"
).read_text(encoding="utf-8")
for name, token in {
    "OI weighting": "open_interest_weight",
    "volume weighting": "volume_weight",
    "weighted score": "total_score",
}.items():
    passed = token in selector
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    failed = failed or not passed

raise SystemExit(1 if failed else 0)
