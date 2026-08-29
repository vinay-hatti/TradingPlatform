#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("reports/market_ingestion/intraday_exclusion_progression/history.jsonl")
if not p.exists(): raise SystemExit("No certification history yet")
rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
print("=== MARKET-SESSION-AWARE SEMANTIC ACTIONABILITY CERTIFICATION ===")
for x in rows[-30:]:
    if x.get("mode")=="PROSPECTIVE_EXCLUSION_BASELINE":
        c=x.get("prospective_comparison") or {}
        print(f'{x["generated_at"][:19]} market_date={x.get("market_date")} session={x.get("market_session")} active={x.get("active_symbols")} excluded={x.get("excluded_symbols")} examined={c.get("prior_excluded_symbols_examined")} hard={c.get("safety_miss_count",0)} actionable={c.get("actionable_miss_count",0)} dynamic_ok={c.get("dynamic_admission_success_count",0)} soft={c.get("soft_progression_count",0)} noise={c.get("recomputation_noise_count",0)} gate={c.get("gate")}')
        if c.get("certification_fail_symbols"):
            print("  fail_symbols="+",".join(c["certification_fail_symbols"][:40]))
    elif x.get("mode")=="EOD_RESEARCH_AUTHORITY_CHECK":
        print(f'{x["generated_at"][:19]} EOD market_date={x.get("market_date")} session={x.get("market_session")} coverage={x.get("reported_option_symbol_coverage")}/{x.get("canonical_symbols")} ready={x.get("eod_authority_ready")} gate={x.get("gate")}')
