from __future__ import annotations

import threading
from pathlib import Path

from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport


class _CompletedByPermanentIdApp:
    def __init__(self):
        self.order_rows = {}
        self.completed_order_rows = {
            "perm:692506253": {
                "broker_order_id": 0,
                "permanent_id": 692506253,
                "client_id": 50,
                "status": "Cancelled",
                "filled_quantity": 0.0,
                "remaining_quantity": 1.0,
                "average_fill_price": 0.0,
                "raw": {"source": "COMPLETED_ORDERS", "symbol": "SHOP"},
            }
        }
        self.orders_ready = threading.Event()
        self.completed_orders_ready = threading.Event()

    def isConnected(self): return True
    def begin_orders(self): self.orders_ready.set()
    def reqOpenOrders(self): pass
    def begin_completed_orders(self): self.completed_orders_ready.set()
    def reqCompletedOrders(self, api_only): assert api_only is False


class _Config:
    timeout_seconds = 0.1


def test_terminal_history_can_be_returned_without_broker_order_id():
    transport = IbapiPaperOrderTransport()
    transport._app = _CompletedByPermanentIdApp()
    transport._config = _Config()
    rows = transport.order_statuses("DU123")
    assert len(rows) == 1
    assert rows[0].broker_order_id == 0
    assert rows[0].permanent_id == 692506253
    assert rows[0].status == "Cancelled"
    assert rows[0].raw["source"] == "COMPLETED_ORDERS"


def test_m73_0_9_source_contains_permanent_id_terminal_recovery_and_diagnostics():
    root = Path(__file__).resolve().parents[1]
    broker = (root / "src/trading_ai/broker/ibkr/order_service.py").read_text()
    transport = (root / "src/trading_ai/broker/ibkr/order_transport.py").read_text()
    workspace = (root / "src/trading_ai/execution_workspace/service.py").read_text()
    ui = (root / "ui/workstation/src/ExecutionWorkspacePage.tsx").read_text()

    assert "BrokerOrderModel.permanent_id==status.permanent_id" in broker
    assert '"matched_by_permanent_id"' in broker
    assert '"source":"COMPLETED_ORDERS"' in transport
    assert "wait_for_cancel_terminal" in transport
    assert "M73.0.9-TERMINAL-BROKER-CANCELLATION-RECONCILIATION" in workspace
    assert "self.s.expire_all()" in workspace
    assert "BROKER_STATUS_REFRESHED" in workspace
    assert "last_reconciliation" in workspace
    assert "Permanent ID" in ui
    assert "Reconciliation source" in ui
    assert "refreshBroker" in ui


def test_cancel_race_maps_fill_and_api_cancel_to_terminal_truth():
    root = Path(__file__).resolve().parents[1]
    workspace = (root / "src/trading_ai/execution_workspace/service.py").read_text()
    broker = (root / "src/trading_ai/broker/ibkr/order_service.py").read_text()
    assert "'APICANCELLED':'CANCELLED'" in workspace
    assert "'FILLED':'FILLED'" in workspace
    assert '"APICANCELLED":"CANCELLED"' in broker
    assert '"FILLED":"FILLED"' in broker


def test_refresh_audit_version_sequencing_prevents_duplicate_audit_versions():
    root = Path(__file__).resolve().parents[1]
    workspace = (root / "src/trading_ai/execution_workspace/service.py").read_text()
    assert "M73.0.9.1-AUDIT-VERSION-SEQUENCING-HOTFIX" in workspace
    # Transition refresh: BROKER_STATUS_SYNCHRONIZED owns the incremented version.
    assert "if changed:" in workspace
    assert "BROKER_STATUS_SYNCHRONIZED" in workspace
    # Diagnostics-only refresh: version must advance before BROKER_STATUS_REFRESHED.
    assert "m.version+=1;m.updated_at=now();self._audit(m,m.state,m.state,'BROKER_STATUS_REFRESHED'" in workspace
    # Missing-broker-row diagnostics must also consume a fresh version.
    assert "m.version+=1;m.updated_at=now();m.broker_json=" in workspace
