#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("reports/market_ingestion/intraday_active_universe_shadow/history.jsonl")
if not p.exists():raise SystemExit("No shadow history yet")
for x in [json.loads(v) for v in p.read_text().splitlines() if v.strip()][-16:]:
    if x["mode"]=="SHADOW_INTRADAY_DECISION":
        print(f'{x["generated_at"][:19]} active={x["proposed_active_count"]}/{x["canonical_symbols"]} avoided_batches={x["projected"]["estimated_symbol_batches_avoided"]} saved_ref_s={x["projected"]["linear_seconds_saved_reference"]} excluded_opp_context={x["opportunity_context_audit"]["excluded_existing_opportunity_count"]}')
    else:print(f'{x["generated_at"][:19]} EOD ready={x["eod_authority_ready"]} coverage={x.get("reported_option_symbol_coverage")}/{x["canonical_symbols"]} morning_recovery={x["next_morning_recovery_required"]}')
