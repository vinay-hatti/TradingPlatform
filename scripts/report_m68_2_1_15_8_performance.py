from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare M68.2.1.15.8 options-ingestion runtime with the certified pre-patch baseline.")
    parser.add_argument("--lifecycle", default="reports/market_ingestion/options_lifecycle_latest.json")
    parser.add_argument("--manifest", default="reports/market_ingestion/options_manifest.json")
    parser.add_argument(
        "--baseline-seconds",
        type=float,
        default=1585.0,
        help="Pre-patch Aug-17 certified options-phase wall time (13:38:07 -> 14:04:32).",
    )
    args = parser.parse_args()

    lifecycle = _load(Path(args.lifecycle))
    manifest = _load(Path(args.manifest))
    cycle_id = manifest.get("latest_cycle_id")
    cycle = dict(manifest.get("cycles", {}).get(cycle_id, {})) if cycle_id else {}
    metadata = dict(cycle.get("metadata", {}))
    performance = dict(metadata.get("performance", {}))

    current = float(lifecycle.get("elapsed_seconds") or 0.0)
    baseline = float(args.baseline_seconds)
    if current <= 0:
        raise RuntimeError("Latest lifecycle report does not contain elapsed_seconds; run options ingestion after M68.2.1.15.8 first.")

    saved = baseline - current
    pct = (saved / baseline * 100.0) if baseline > 0 else 0.0
    speedup = (baseline / current) if current > 0 else 0.0

    print("=== M68.2.1.15.8 OPTIONS PERFORMANCE ===")
    print(f"cycle_id                 : {cycle_id}")
    print(f"baseline_seconds          : {baseline:.2f}")
    print(f"current_seconds           : {current:.2f}")
    print(f"time_saved_seconds        : {saved:.2f}")
    print(f"runtime_reduction_pct     : {pct:.2f}%")
    print(f"speedup                   : {speedup:.3f}x")
    if performance:
        print("\n--- Current-cycle stage timings ---")
        for key in (
            "capture_seconds",
            "snapshot_finalize_seconds",
            "derived_parallel_wall_seconds",
            "volatility_seconds",
            "liquidity_seconds",
            "dealer_seconds",
            "domain_cycle_seconds",
            "dealer_workers",
            "derived_execution_mode",
        ):
            if key in performance:
                print(f"{key:<28}: {performance[key]}")
    print("\n--- Lineage integrity ---")
    print(f"governed_option_rows      : {metadata.get('governed_option_rows')}")
    print(f"valid_records             : {metadata.get('valid_records')}")
    print(f"stale_daily_rows_pruned   : {metadata.get('stale_daily_rows_pruned')}")
    print(f"completed_successfully    : {metadata.get('completed_successfully')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
