from __future__ import annotations

import json

from sqlalchemy import inspect

from trading_ai.broker.ibkr import IbkrPaperOrderGovernanceService
from trading_ai.database.engine import engine
from trading_ai.database.session import SessionLocal


def main() -> None:
    expected_tables = {
        "broker_order_controls",
        "broker_orders",
        "broker_executions",
    }
    existing_tables = set(inspect(engine).get_table_names())
    missing_tables = sorted(expected_tables - existing_tables)

    result: dict[str, object] = {
        "milestone": 50,
        "phase": "IBKR_PAPER_ORDER_ROUTING",
        "missing_tables": missing_tables,
        "live_trading_enabled": False,
        "paper_only": True,
    }

    if missing_tables:
        result["status"] = "MIGRATION_REQUIRED"
    else:
        try:
            governance = IbkrPaperOrderGovernanceService(SessionLocal)
            result["control"] = governance.status("PAPER-PRIMARY")
            result["status"] = "READY_FOR_EXPLICIT_ACTIVATION"
        except Exception as exc:
            result["status"] = "ACCOUNT_BINDING_REQUIRED"
            result["error"] = str(exc)

    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
