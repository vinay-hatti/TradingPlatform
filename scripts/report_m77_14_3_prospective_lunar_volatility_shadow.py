#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

p=Path("reports/m77/m77_14_3_lunar_forward_shadow/history.jsonl")
if not p.exists():
    raise SystemExit("No M77.14.3 forward-shadow history yet")

rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
captures=[x for x in rows if x.get("mode")=="CAPTURE"]
matured=[x for x in rows if x.get("mode")=="MATURED"]
eligible_matured=[x for x in matured if x.get("counts_toward_review_gate", True)]
diagnostic_matured=[x for x in matured if not x.get("counts_toward_review_gate", True)]

episodes={}
for x in captures:
    if x.get("event_active") and x.get("episode_id"):
        episodes.setdefault(x["episode_id"],[]).append(x)

print("=== M77.14.3 PROSPECTIVE LUNAR VOLATILITY SHADOW ===")
print("capture_rows:",len(captures))
print("event_episodes_seen:",len(episodes))
print("completed_episodes:",len(eligible_matured))
print("certification_eligible_completed_episodes:",len(eligible_matured))
print("diagnostic_completed_episodes:",len(diagnostic_matured))
print("production_authority_effect: False")
print("production_model_or_weight_change: False")

if eligible_matured:
    vals=[x["realized_10d_absolute_return"] for x in eligible_matured]
    print("prospective_mean_absolute_return:",sum(vals)/len(vals))
    print("historical_event_mean:",eligible_matured[0]["historical_event_mean"])
    print("historical_complement_mean:",eligible_matured[0]["historical_complement_mean"])
    print("suppression_successes:",sum(bool(x["suppression_vs_historical_complement"]) for x in eligible_matured),"/",len(eligible_matured))
    print("\n--- COMPLETED EPISODES ---")
    for x in matured:
        print(
          x["episode_id"],
          "entry",x["entry_session"],
          "exit",x["exit_session"],
          "abs10d",x["realized_10d_absolute_return"],
          "regime",x.get("pit_regime_at_entry"),
          "suppressed",x["suppression_vs_historical_complement"],
        )
else:
    print("No completed 10-session episodes yet.")

print("\nReview gate: >=12 completed episodes before any contextual-integration decision.")
