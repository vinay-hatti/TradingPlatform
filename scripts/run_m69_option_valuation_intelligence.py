import argparse
import json

from trading_ai.database.session import SessionLocal
from trading_ai.option_valuation_intelligence.service import InstitutionalOptionValuationService

p = argparse.ArgumentParser()
p.add_argument("--limit", type=int)
p.add_argument("--scope", choices=("current", "all"), default="current")
p.add_argument("--opportunity-id", action="append", default=[])
a = p.parse_args()

if a.scope == "all":
    scope = "ALL"
    opportunity_ids = None
else:
    scope = "CURRENT_RUN"
    opportunity_ids = tuple(a.opportunity_id)
    if not opportunity_ids:
        raise SystemExit(
            "--scope current requires at least one --opportunity-id. "
            "Use --scope all only for an intentional historical rebuild."
        )

print(json.dumps(
    InstitutionalOptionValuationService(SessionLocal).build(
        limit=a.limit, opportunity_ids=opportunity_ids, scope=scope
    ),
    indent=2, sort_keys=True,
))
