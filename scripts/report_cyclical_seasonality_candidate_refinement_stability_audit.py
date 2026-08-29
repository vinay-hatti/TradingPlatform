#!/usr/bin/env python3
import argparse,json
from pathlib import Path
def f(x,d=3):return "N/A" if x is None else f"{float(x):.{d}f}"
ap=argparse.ArgumentParser();ap.add_argument("--input",default="reports/cyclical_seasonality/cyclical_seasonality_candidate_refinement_stability_audit.json");ap.add_argument("--top",type=int,default=50);a=ap.parse_args()
d=json.loads(Path(a.input).read_text())
print("=== CYCLICAL & SEASONALITY — CANDIDATE REFINEMENT & STABILITY AUDIT ===");print("Version:",d["version"]);print("Summary:",d["summary"]);print("Disposition:",d["disposition"]);print()
for cls in ("NEAR_CERTIFICATION_FDR_ONLY","CROSS_YEAR_UNSTABLE","INSUFFICIENT_CONTROL_COVERAGE","STATISTICALLY_UNSUPPORTED"):
 rows=[x for x in d["candidates"] if x["classification"]==cls];print(f"--- {cls} ({len(rows)}) ---")
 for x in rows[:a.top]:
  y=x["full_year"];h=x["hierarchical_testing_diagnostic"];c=x["symbol_membership_concentration"]
  print(f'{x["factor_family"]} | {x["factor"]}={x["state"]} {x["direction"]} @{x["horizon"]}d ex={[round(v,3) if v is not None else None for v in y["matched_excess_pct"]]} q={[round(v,5) if v is not None else None for v in y["fdr_q"]]} N={y["matched_n"]} cov={[round(v,1) if v is not None else None for v in y["coverage_pct"]]} familyQ={f(h["family_qvalue"],5)} withinQ={f(h["within_family_candidate_qvalue"],5)} symbols={c["symbols"]} top10share={f(c["top_10_symbol_share_pct"],2)}%')
 print()
print("Production/shadow activation: NONE")
