#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument(
    "--input",
    default=(
        "reports/cyclical_seasonality/"
        "cyclical_seasonality_walk_forward_certification.json"
    ),
)
ap.add_argument("--top", type=int, default=50)
a = ap.parse_args()

d = json.loads(Path(a.input).read_text())

print("=== CYCLICAL & SEASONALITY — PURGED EXPANDING-WINDOW WALK-FORWARD ===")
print("Version:", d["version"])
print("Summary:", d["summary"])
print()

for f in d["folds"]:
    print(
        f'Fold {f["holdout_year"]} [{f["holdout_credit"]}] '
        f'selected={f["selected"]} pass={f["passed"]} fail={f["failed"]}'
    )

print()
print("--- WALK-FORWARD SUPPORTED ---")
rows = [
    x for x in d["cohorts"]
    if x["status"] == "WALK_FORWARD_SUPPORTED"
]
for x in rows[: a.top]:
    print(
        f'{x["factor_family"]} | {x["factor"]}={x["state"]} '
        f'{x["direction"]} @{x["horizon"]}d '
        f'holdouts={x["selected_holdouts"]} '
        f'full_year={x["full_year_holdouts"]} '
        f'minN={x["minimum_passed_holdout_n"]} '
        f'minRet={x["minimum_passed_holdout_thesis_return_pct"]:.3f}% '
        f'minHit={x["minimum_passed_holdout_hit_rate_pct"]:.2f}%'
    )

print()
print("Production authority effect: NONE")
print("Production thresholds/weights: UNCHANGED")
print("Automatic shadow activation: NONE")
print("Next gate: FOLD-NATIVE MATCHED-CONTROL HARDENING + SHADOW CERTIFICATION")
