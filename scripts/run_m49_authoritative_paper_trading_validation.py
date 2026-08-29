from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import inspect

from trading_ai.authoritative_paper_trading.service import AuthoritativePaperAccountService
from trading_ai.database.session import engine

EXPECTED_TABLES = {
    "canonical_orders",
    "canonical_order_events",
    "paper_executions",
    "paper_fills",
    "portfolio_cash_reservations",
    "paper_trading_sessions",
    "paper_automation_checkpoints",
    "paper_trading_controls",
    "paper_position_marks",
    "paper_position_lifecycle_events",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Milestone 49 authoritative paper-trading persistence")
    parser.add_argument("--account-id", default="PAPER-PRIMARY")
    parser.add_argument("--report", default="reports/m49/authoritative_persistence_validation.json")
    args = parser.parse_args()

    tables = set(inspect(engine).get_table_names())
    missing = sorted(EXPECTED_TABLES - tables)
    service = AuthoritativePaperAccountService()
    account = None
    reconciliation = None
    try:
        account = service.account_summary(args.account_id)
        reconciliation = service.reconcile(args.account_id)
    except KeyError:
        pass

    report = {
        "milestone": 49,
        "status": "READY" if not missing else "FAILED",
        "expected_tables": sorted(EXPECTED_TABLES),
        "missing_tables": missing,
        "account_id": args.account_id,
        "account": account,
        "reconciliation": reconciliation,
        "governance": {
            "database_authoritative": True,
            "json_runtime_state_authoritative": False,
            "live_trading_enabled": False,
            "paper_only": True,
        },
    }
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
