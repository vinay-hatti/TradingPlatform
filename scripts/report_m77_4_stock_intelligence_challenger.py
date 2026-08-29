#!/usr/bin/env python
from __future__ import annotations
import argparse, json
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="reports/m77/m77_4_walk_forward_challenger_certification.json")
    p.add_argument("--top", type=int, default=30)
    a = p.parse_args()
    d = json.loads(Path(a.input).read_text())
    print("=== M77.4 GOVERNED CHALLENGER WALK-FORWARD ===")
    print("Version:", d["challenger_version"])
    print("Coverage:", d["coverage"])
    print("Summary:", d["summary"])
    print()
    for fold in d["folds"]:
        print(
            f'Fold {fold["validation_year"]} [{fold["validation_period_status"]}] '
            f'selected={fold["selected_pre_holdout_count"]} '
            f'pass={fold["selected_pass_count"]} fail={fold["selected_fail_count"]}'
        )
    print("\n--- WALK-FORWARD SUPPORTED COHORTS ---")
    eligible = [x for x in d["certification"] if x["research_challenger_eligible"]]
    for x in eligible[:a.top]:
        print(
            x["candidate_horizon_id"],
            "holdouts=", x["selected_holdout_folds"],
            "passed=", x["passed_holdout_folds"],
            "status=", x["certification_status"],
        )
    print("\nProduction champion change: NONE")
    print("Production thresholds/weights: UNCHANGED")
    print("Bearish inversion: PROHIBITED")

if __name__ == "__main__":
    main()
