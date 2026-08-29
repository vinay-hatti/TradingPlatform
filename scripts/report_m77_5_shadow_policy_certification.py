#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_INPUT = Path("reports/m77/m77_5_shadow_policy_certification.json")


def _fmt(v, digits=3):
    if v is None:
        return "N/A"
    return f"{float(v):.{digits}f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--top", type=int, default=40)
    args = parser.parse_args()

    d = json.loads(Path(args.input).read_text())
    print("=== M77.5 WALK-FORWARD STABILITY / INCREMENTAL EDGE / SHADOW POLICY ===")
    print("Version:", d["version"])
    print("Coverage:", d["coverage"])
    print("Summary:", d["summary"])
    print()

    groups = [
        ("SHADOW POLICY CERTIFIED", "SHADOW_POLICY_CERTIFIED"),
        ("SUPPORTED, NOT SHADOW CERTIFIED", "WALK_FORWARD_SUPPORTED_NOT_SHADOW_CERTIFIED"),
        ("OBSERVATIONAL SUPPORT ONLY", "OBSERVATIONAL_WALK_FORWARD_SUPPORT"),
    ]
    shown = 0
    for title, status in groups:
        rows = [r for r in d["certification"] if r["status"] == status]
        print(f"--- {title} ({len(rows)}) ---")
        for r in rows:
            if shown >= args.top:
                break
            print(
                f'{r["candidate_horizon_id"]} '
                f'holdouts={r["selected_holdout_folds"]} '
                f'full_year={r["full_year_holdout_folds"]} '
                f'minN={r["min_non_overlapping_observations"]} '
                f'minRet={_fmt(r["min_thesis_return_pct"])}% '
                f'minHit={_fmt(r["min_directional_hit_rate_pct"],2)}% '
                f'minExcess={_fmt(r["min_matched_excess_pct"])}%'
            )
            if r["failure_reasons"]:
                print("  reasons:", ",".join(r["failure_reasons"]))
            shown += 1
        print()
        if shown >= args.top:
            break

    print("Production champion change: NONE")
    print("Production thresholds/weights/decisions: UNCHANGED")
    print("Database writes: NONE")
    print("Automatic bearish inversion: PROHIBITED")
    print("2026 partial year: SUPPORTING EVIDENCE ONLY, NOT FULL-YEAR CREDIT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
