#!/usr/bin/env python3
import argparse,json
from pathlib import Path

p=Path("reports/m77/m77_15_7_long_history_frozen_hypothesis_replication.json")
if not p.exists():
    raise SystemExit("Run M77.15.7 first")

ap=argparse.ArgumentParser()
ap.add_argument("--show-supported",action="store_true")
ap.add_argument("--show-cross-authority",action="store_true")
ap.add_argument("--show-top",type=int,default=80)
a=ap.parse_args()

x=json.loads(p.read_text())
print("=== M77.15.7 LONG-HISTORY FROZEN-HYPOTHESIS REPLICATION ===")
for k in (
    "status","authority_type","result_count",
    "long_history_research_supported_candidate_count",
    "recent_canonical_supported_key_count",
    "cross_authority_supported_for_dependence_robust_confirmation_count",
    "next_step","production_authority_effect"
):
    print(f"{k}: {x.get(k)}")

print("\n--- AUTHORITY ---")
print(x["authority_certification"])
print("frozen_eras:",x["frozen_eras"])

rows=sorted(
    x["results"],
    key=lambda r:(r.get("bh_q",1.0),-abs(r.get("incremental_vs_complement") or 0))
)

print("\n--- TOP LONG-HISTORY RESULTS ---")
for r in rows[:a.show_top]:
    label=r.get("factor") or r.get("event_family")
    level=r.get("level")
    descriptor=f"{label}={level}" if level is not None else str(label)
    print(
        f'{r["family"]} {r["target"]} {r["horizon_sessions"]}d '
        f'{descriptor} outcome={r["outcome"]} N={r["event_n"]} '
        f'inc_comp={r.get("incremental_vs_complement")} '
        f'inc_match={r.get("incremental_vs_weekday_month")} '
        f'q={r.get("bh_q"):.5g} long={r["long_history_status"]} '
        f'cross={r["cross_authority_status"]}'
    )

if a.show_supported:
    print("\n--- LONG-HISTORY RESEARCH SUPPORTED CANDIDATES ---")
    good=[r for r in rows if r["long_history_status"]=="RESEARCH_SUPPORTED_CANDIDATE"]
    if not good: print("NONE")
    for r in good:
        print(r["key"])
        print("  gate:",r["long_history_gate"])
        print("  eras:",r["era_stats"])
        print("  cross_authority:",r["cross_authority"])

if a.show_cross_authority:
    print("\n--- CROSS-AUTHORITY SURVIVORS ---")
    good=[r for r in rows if r["cross_authority_status"]=="SUPPORTED_FOR_DEPENDENCE_ROBUST_CONFIRMATION"]
    if not good: print("NONE")
    for r in good:
        print(r["key"])
        print("  cross_authority:",r["cross_authority"])
