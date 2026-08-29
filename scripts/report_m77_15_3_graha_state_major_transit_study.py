#!/usr/bin/env python3
import argparse,json
from pathlib import Path
cert=Path("reports/m77/m77_15_3_graha_registry_certification.json")
study=Path("reports/m77/m77_15_3_graha_state_major_transit_study.json")
ap=argparse.ArgumentParser();ap.add_argument("--show-supported",action="store_true");ap.add_argument("--show-top",type=int,default=50);a=ap.parse_args()
print("=== M77.15.3 GRAHA STATE & MAJOR TRANSIT STUDY ===")
if cert.exists():
    c=json.loads(cert.read_text())
    print("registry_certification:",c["acceptance"])
    print("registry_max_jpl_error_deg:",c["max_angular_error_deg"])
    print("comparison_contract:",c.get("comparison_contract"))
    if c.get("max_geometric_diagnostic_error_deg") is not None:
        print("old_geometric_diagnostic_max_error_deg:",c["max_geometric_diagnostic_error_deg"])
if not study.exists():
    print("No financial study artifact yet.");raise SystemExit(0)
x=json.loads(study.read_text())
for k in ("status","targets","result_count","research_supported_candidate_count","next_step","production_authority_effect"):
    print(f"{k}: {x.get(k)}")
rows=sorted(x["results"],key=lambda r:(r.get("bh_q",1.0),-abs(r.get("incremental_vs_complement") or 0)))
print("\n--- TOP PRE-REGISTERED RESULTS ---")
for r in rows[:a.show_top]:
    print(f'{r["target"]} {r["horizon_sessions"]}d {r["factor"]}={r["level"]} outcome={r["outcome"]} N={r["event_n"]} event={r["event_mean"]:.6f} inc_comp={r.get("incremental_vs_complement")} inc_match={r.get("incremental_vs_weekday_month_regime")} q={r.get("bh_q"):.5g} status={r["status"]}')
if a.show_supported:
    print("\n--- RESEARCH SUPPORTED CANDIDATES ---")
    good=[r for r in rows if r["status"]=="RESEARCH_SUPPORTED_CANDIDATE"]
    if not good:print("NONE")
    for r in good:
        print(r["key"]);print("  gate:",r["research_gate"])
