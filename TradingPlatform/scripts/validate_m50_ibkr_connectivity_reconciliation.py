from __future__ import annotations

import json
from importlib.util import find_spec

from sqlalchemy import inspect

from trading_ai.database.engine import engine


def main() -> None:
    expected = {
        "broker_account_bindings",
        "broker_account_snapshots",
        "broker_position_snapshots",
        "broker_reconciliation_runs",
        "portfolio_accounts",
        "portfolio_positions",
    }
    tables = set(inspect(engine).get_table_names())
    missing = sorted(expected - tables)
    ibapi_installed = find_spec("ibapi") is not None
    status = "READY_FOR_TWS_CONNECTION" if not missing and ibapi_installed else (
        "IBAPI_INSTALLATION_REQUIRED" if not missing else "NOT_READY"
    )
    print(json.dumps({
        "milestone": 50,
        "phase": "IBKR_CONNECTIVITY_AND_RECONCILIATION",
        "status": status,
        "missing_tables": missing,
        "ibapi_installed": ibapi_installed,
        "paper_only": True,
        "read_only": True,
        "live_trading_enabled": False,
        "order_submission_enabled": False,
        "next_action": (
            "Start TWS/IB Gateway paper session and run test_ibkr_paper_connection.py."
            if status == "READY_FOR_TWS_CONNECTION"
            else "Install the official IBKR TWS Python API from the IBKR API download."
        ),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
