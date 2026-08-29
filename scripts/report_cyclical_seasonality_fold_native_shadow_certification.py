#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def f(v, d=3):
    return "N/A" if v is None else f"{float(v):.{d}f}"


ap = argparse.ArgumentParser()
ap.add_argument(
    "--input",
    default=(
        "reports/cyclical_seasonality/"
        "cyclical_seasonality_fold_native_shadow_certification.json"
    ),
)
ap.add_argument("--top", type=int, default=60)
a = ap.parse_args()

d = json.loads(Path(a.input).read_text())

print("=== CYCLICAL & SEASONALITY — FOLD-NATIVE MATCHED-CONTROL SHADOW CERTIFICATION ===")
print("Version:", d["version"])
print("Summary:", d["summary"])
print()
print("Control:", d["methodology"]["matched_control_contract"])
print()

for tier in ("SHADOW_CERTIFIED_TIER_1", "SHADOW_CERTIFIED_TIER_2"):
    rows = [
        x for x in d["certifications"]
        if x["shadow_certification_status"] == tier
    ]
    print(f"--- {tier} ({len(rows)}) ---")
    for x in rows[: a.top]:
        folds = {
            r["holdout_year"]: r
            for r in x["folds"]
        }
        f24 = folds.get(2024, {})
        f25 = folds.get(2025, {})
        f26 = folds.get(2026, {})
        def ex(r):
            return (r.get("matched") or {}).get(
                "matched_excess_thesis_return_avg_pct"
            )
        def q(r):
            return (r.get("matched") or {}).get("matched_excess_fdr_qvalue")
        print(
            f'{x["factor_family"]} | {x["factor"]}={x["state"]} '
            f'{x["direction"]} @{x["horizon"]}d '
            f'2024ex={f(ex(f24))}% q={f(q(f24),5)} '
            f'2025ex={f(ex(f25))}% q={f(q(f25),5)} '
            f'2026ex={f(ex(f26))}% q={f(q(f26),5)} '
            f'minFullYearEx={f(x["full_year_min_matched_excess_pct"])}%'
        )
    print()

print("--- REDUNDANCY ---")
print(
    "components=",
    len(d["redundancy"]["components"]),
    "pairs=",
    len(d["redundancy"]["correlated_pairs"]),
    "threshold=",
    d["redundancy"]["jaccard_threshold"],
)
print()
print("Production authority effect: NONE")
print("Automatic shadow activation: NONE")
print("Next gate: LIVE-FORWARD CYCLICAL/SEASONALITY SHADOW CAPTURE ONLY")
