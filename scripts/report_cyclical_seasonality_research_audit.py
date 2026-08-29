#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def f(v, d=3):
    return "N/A" if v is None else f"{float(v):.{d}f}"


ap = argparse.ArgumentParser()
ap.add_argument(
    "--input",
    default="reports/cyclical_seasonality/cyclical_seasonality_research_audit.json",
)
ap.add_argument("--top", type=int, default=50)
a = ap.parse_args()
d = json.loads(Path(a.input).read_text())

print("=== CYCLICAL & SEASONALITY INTELLIGENCE — RESEARCH AUDIT 1.1 ===")
print("Version:", d["version"])
print("Coverage:", d["coverage"])
print("Screening:", d["screening_summary"])
print("Exact cross-factor aliases:", len(d.get("alias_diagnostics", {}).get("exact_alias_pairs", [])))
print()

print("=== INDEPENDENT FACTOR FAMILY RANKING ===")
for x in d.get("independent_factor_family_ranking", []):
    print(
        f'{x["factor_family"]}: qualified={x["qualified_hypotheses"]} '
        f'top={x["top_factor"]}={x["top_state"]} {x["top_direction"]} '
        f'@{x["top_horizon"]}d excess={f(x["top_matched_excess_thesis_return_avg_pct"])}% '
        f'q={f(x["top_fdr_qvalue"], 5)}'
    )

print()
print("=== WALK-FORWARD-ELIGIBLE HYPOTHESES ===")
for x in [
    e for e in d["evidence"]
    if e["research_screen"] == "HYPOTHESIS_WORTH_WALK_FORWARD"
][: a.top]:
    c = x["matched_control"]
    print(
        f'{x["factor_family"]} | {x["factor"]}={x["state"]} '
        f'{x["direction"]} @{x["horizon"]}d '
        f'N={x["non_overlapping_observations"]} '
        f'raw={f(x["non_overlapping_raw_underlying_return_avg_pct"])}% '
        f'thesis={f(x["non_overlapping_thesis_return_avg_pct"])}% '
        f'hit={f(x["non_overlapping_directional_hit_rate_pct"], 2)}% '
        f'years={x["positive_years"]}/{x["qualified_years"]} '
        f'excess={f(c["matched_excess_thesis_return_avg_pct"])}% '
        f'q={f(c["matched_excess_fdr_qvalue"], 5)}'
    )

print("\nProduction changes: NONE")
print("Next gate: PURGED EXPANDING-WINDOW WALK-FORWARD ONLY")
