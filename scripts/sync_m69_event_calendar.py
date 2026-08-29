from __future__ import annotations
import argparse, json
from trading_ai.database.session import SessionLocal
from trading_ai.option_valuation_intelligence.events import EventCalendarSynchronizationService, EventSyncPolicy
p=argparse.ArgumentParser(description='Synchronize verified M69.6 event calendars idempotently')
p.add_argument('--horizon-months',type=int,default=6,choices=(6,))
p.add_argument('--timeout-seconds',type=float,default=45.0)
p.add_argument(
    '--accept-governed-cache',
    action='store_true',
    help=(
        'Return success when every degraded source uses a non-empty '
        'governed official cache.'
    ),
)
a=p.parse_args()
result=EventCalendarSynchronizationService(SessionLocal,EventSyncPolicy(horizon_months=a.horizon_months,timeout_seconds=a.timeout_seconds)).synchronize()
status = str(result.get("status") or "").upper()
source_results = result.get("source_results")


def governed_source_is_usable(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False

    source_status = str(payload.get("status") or "").upper()
    if source_status == "READY":
        return True

    if source_status != "DEGRADED_CACHE":
        return False

    try:
        return int(payload.get("fetched") or 0) > 0
    except (TypeError, ValueError):
        return False


governed_degraded = (
    status == "DEGRADED"
    and isinstance(source_results, dict)
    and bool(source_results)
    and all(
        governed_source_is_usable(payload)
        for payload in source_results.values()
    )
)

accepted = (
    status == "READY"
    or (a.accept_governed_cache and governed_degraded)
)

result["cli_exit_disposition"] = (
    "READY"
    if status == "READY"
    else "GOVERNED_DEGRADED_ACCEPTED"
    if accepted
    else "FAILED"
)

print(json.dumps(result, indent=2, sort_keys=True))
raise SystemExit(0 if accepted else 1)
