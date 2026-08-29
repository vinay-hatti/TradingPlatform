#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

p=Path("reports/m77/m77_14_1_astronomical_incremental_certification.json")
ap=argparse.ArgumentParser()
ap.add_argument("--show-supported",action="store_true")
ap.add_argument("--show-top",type=int,default=30)
a=ap.parse_args()

if not p.exists():
    raise SystemExit("Run M77.14.1 first")

x=json.loads(p.read_text())
print("=== M77.14.1 INCREMENTAL BASELINE / PERMUTATION / OUTCOME HARDENING ===")
for k in (
    "status","targets","result_count","research_supported_count",
    "permutations_per_test","traditional_astrology_disposition",
    "next_step","production_authority_effect",
):
    print(f"{k}: {x.get(k)}")

rows=sorted(
    x["results"],
    key=lambda r:(r.get("bh_q",1.0),-abs((r.get("controls") or {}).get("incremental_vs_complement") or 0)),
)

print("\n--- TOP PRE-REGISTERED RESULTS ---")
for r in rows[:a.show_top]:
    e=r["event"]; c=r["controls"]
    print(
      f'{r["target"]} {r["horizon_sessions"]}d {r["hypothesis"]} '
      f'outcome={r["outcome"]} family={r["family"]} N={e["n"]} '
      f'event={e["mean"]:.6f} inc_comp={c.get("incremental_vs_complement")} '
      f'inc_regime={c.get("incremental_vs_regime")} '
      f'inc_regcal={c.get("incremental_vs_regime_calendar")} '
      f'q={r.get("bh_q"):.5g} status={r["status"]}'
    )

if a.show_supported:
    print("\n--- RESEARCH SUPPORTED ---")
    good=[r for r in rows if r["status"]=="RESEARCH_SUPPORTED"]
    if not good:
        print("NONE")
    for r in good:
        print(r["key"])
        print("  event:",r["event"])
        print("  controls:",r["controls"])
        print("  permutation:",r["permutation"])
        print("  gate:",r["research_gate"])
