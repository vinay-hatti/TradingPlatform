from __future__ import annotations

import json
from sqlalchemy import inspect
from trading_ai.database.engine import engine

EXPECTED = {
    "broker_account_bindings", "broker_account_snapshots",
    "broker_position_snapshots", "broker_reconciliation_runs",
}


def main() -> None:
    present = set(inspect(engine).get_table_names())
    missing = sorted(EXPECTED - present)
    payload = {
        "milestone": 50,
        "phase": "IBKR_PAPER_ACCOUNT_FOUNDATION",
        "status": "READY_FOR_ACCOUNT_REGISTRATION" if not missing else "FAILED",
        "missing_tables": missing,
        "paper_only": True,
        "live_trading_enabled": False,
        "credentials_required": False,
        "next_action": "Register the IBKR DU paper account after this validation passes.",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
