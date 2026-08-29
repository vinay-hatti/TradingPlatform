#!/usr/bin/env python3
import argparse,json
from pathlib import Path

p=Path("reports/m77/m77_15_4_rahu_ketu_eclipse_planetary_geometry_event_study.json")
ap=argparse.ArgumentParser()
ap.add_argument("--show-supported",action="store_true")
ap.add_argument("--show-top",type=int,default=60)
a=ap.parse_args()

if not p.exists():
    raise SystemExit("Run M77.15.4 first")

x=json.loads(p.read_text())
print("=== M77.15.4 RAHU/KETU, ECLIPSE & PLANETARY GEOMETRY EVENT STUDY ===")
for k in ("status","targets","event_family_counts","result_count","research_supported_candidate_count","next_step","production_authority_effect"):
    print(f"{k}: {x.get(k)}")

rows=sorted(x["results"],key=lambda r:(r.get("bh_q",1.0),-abs(r.get("incremental_vs_complement") or 0)))

print("\n--- TOP PRE-REGISTERED EVENT RESULTS ---")
for r in rows[:a.show_top]:
    print(f'{r["target"]} {r["horizon_sessions"]}d {r["event_family"]} outcome={r["outcome"]} N={r["event_n"]} event={r["event_mean"]:.6f} inc_comp={r.get("incremental_vs_complement")} inc_match={r.get("incremental_vs_weekday_month_regime")} q={r.get("bh_q"):.5g} status={r["status"]}')

if a.show_supported:
    print("\n--- RESEARCH SUPPORTED CANDIDATES ---")
    good=[r for r in rows if r["status"]=="RESEARCH_SUPPORTED_CANDIDATE"]
    if not good:
        print("NONE")
    for r in good:
        print(r["key"])
        print("  gate:",r["research_gate"])
