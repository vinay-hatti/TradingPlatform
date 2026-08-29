from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run(script: str) -> None:
    command = [sys.executable, str(ROOT / script)]
    print()
    print("=" * 72)
    print("Running:", " ".join(command))
    print("=" * 72)
    completed = subprocess.run(command, cwd=ROOT)
    if completed.returncode != 0:
        raise SystemExit(
            f"{script} failed with exit code {completed.returncode}"
        )


def verify_file(relative: str, required: list[str]) -> None:
    path = ROOT / relative
    if not path.exists():
        raise SystemExit(f"Missing required file: {relative}")

    text = path.read_text(encoding="utf-8")
    missing = [token for token in required if token not in text]
    if missing:
        raise SystemExit(
            f"{relative} is missing required integration tokens: {missing}"
        )


def main() -> None:
    run("scripts/apply_live_option_data_integration.py")

    verify_file(
        "src/trading_ai/daily/scanner.py",
        [
            "LiveOptionContractSelector",
            "option_data_mode",
            "contract_ticker",
        ],
    )

    run(
        "scripts/"
        "apply_liquidity_weighted_contract_selection.py"
    )

    verify_file(
        "src/trading_ai/daily/models.py",
        [
            "spread_pct",
            "contract_selection_score",
            "liquidity_score",
            "open_interest_selection_score",
            "volume_selection_score",
        ],
    )
    verify_file(
        "src/trading_ai/daily/trade_candidate.py",
        [
            "spread_pct",
            "contract_selection_score",
            "liquidity_score",
            "open_interest_selection_score",
            "volume_selection_score",
        ],
    )
    verify_file(
        "src/trading_ai/options/live_contract_selector.py",
        [
            "open_interest_weight",
            "volume_weight",
            "total_score",
            "liquidity_score",
        ],
    )
    verify_file(
        "scripts/run_daily_scan.py",
        [
            "--option-data-mode",
            "--option-oi-weight",
            "--option-volume-weight",
        ],
    )

    print()
    print("=" * 72)
    print("Combined live-option and liquidity-weighted integration succeeded.")
    print("=" * 72)


if __name__ == "__main__":
    main()
