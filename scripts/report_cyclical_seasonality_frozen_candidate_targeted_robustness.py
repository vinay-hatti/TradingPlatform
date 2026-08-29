#!/usr/bin/env python3
import argparse,json
from pathlib import Path

ap=argparse.ArgumentParser()
ap.add_argument("--input",default="reports/cyclical_seasonality/cyclical_seasonality_frozen_candidate_targeted_robustness.json")
a=ap.parse_args()
d=json.loads(Path(a.input).read_text())

print("=== CYCLICAL & SEASONALITY — FROZEN CANDIDATE TARGETED ROBUSTNESS ===")
print("Version:",d["version"])
print("Candidate:",d["frozen_candidate"]["candidate_id"])
print()
print("--- FULL-YEAR EVIDENCE ---")
for x in d["full_year_metrics"]:
    print(f'{x["year"]}: excess={x["matched_excess_pct"]:+.3f}% thesis={x["thesis_return_pct"]:+.3f}% '
          f'q={x["fdr_q"]:.5f} coverage={x["coverage_pct"]:.2f}% N={x["matched_n"]}')
print()
print("--- STRICT EXISTING GATE ---")
for k,v in d["strict_checks"].items():
    print(f"{k}: {'PASS' if v else 'FAIL'}")
print("Strict historical certified:",d["strict_historical_certified"])
print()
o=d["observation_level_robustness"]
print("--- OBSERVATION-LEVEL ROBUSTNESS ---")
print("Available:",o.get("available"))
if not o.get("available"):
    print("Reason:",o.get("reason"))
else:
    print("Rows:",o.get("rows"),"Symbols:",o.get("symbols"))
    print("Bootstrap mean 95% CI:",o.get("bootstrap_mean_pct_95_ci"))
    print("Quarter stability:",o.get("quarter_stability"))
    print("Leave-symbol-cluster-out positive:",
          f'{o.get("leave_symbol_hash_cluster_out_positive")}/{o.get("leave_symbol_hash_cluster_out_total")}')
print()
print("Disposition:",d["disposition"])
print("Next action:",d["next_action"])
print("Production/shadow activation: NONE")
