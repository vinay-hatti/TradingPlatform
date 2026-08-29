#!/usr/bin/env python3
import argparse,json
from pathlib import Path
p=Path("reports/m77/m77_16_vedic_predictive_hypotheses_ii.json")
if not p.exists(): raise SystemExit("Run M77.16 first")
ap=argparse.ArgumentParser(); ap.add_argument("--show-supported",action="store_true"); ap.add_argument("--show-top",type=int,default=80)
a=ap.parse_args(); x=json.loads(p.read_text())
print("=== M77.16 VEDIC PREDICTIVE HYPOTHESES II ===")
for k in ("status","hypothesis_result_count","long_history_research_supported_candidate_count","atichari_velocity_threshold_deg_per_day","next_step","production_authority_effect"): print(f"{k}: {x.get(k)}")
print("authority:",x["authority"])
print("blocked_hypotheses:",x["blocked_hypotheses"])
rows=sorted(x["results"],key=lambda r:(r.get("bh_q",1.0),-abs(r.get("incremental_vs_complement") or 0)))
print("\n--- TOP RESULTS ---")
for r in rows[:a.show_top]:
    extra=f' {r.get("feature")}={r.get("level")}' if r.get("feature") else ""
    print(f'{r["hypothesis"]}{extra} target={r["target"]} instrument={r["research_instrument"]} h={r["horizon_sessions"]} outcome={r["outcome"]} N={r["event_n"]} inc_comp={r["incremental_vs_complement"]} inc_match={r["incremental_vs_weekday_month"]} q={r["bh_q"]:.5g} status={r["status"]}')
if a.show_supported:
    print("\n--- LONG-HISTORY SUPPORTED ---")
    good=[r for r in rows if r["status"]=="LONG_HISTORY_RESEARCH_SUPPORTED_CANDIDATE"]
    if not good: print("NONE")
    for r in good:
        print(r["key"]); print("  gate:",r["research_gate"]); print("  eras:",r["era_stats"])
