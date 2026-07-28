from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict
from decimal import Decimal
import threading
import time
from typing import Any

from .models import (
    IbkrAccountSummary,
    IbkrConnectionStatus,
    IbkrPaperConnectionConfig,
    IbkrPositionSnapshot,
    utc_now_iso,
)


class IbkrTransport(ABC):
    @abstractmethod
    def connect(self, config: IbkrPaperConnectionConfig) -> IbkrConnectionStatus: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def account_summary(self, account_id: str) -> IbkrAccountSummary: ...

    @abstractmethod
    def positions(self, account_id: str) -> list[IbkrPositionSnapshot]: ...


class IbapiTransport(IbkrTransport):
    """Read-only transport for the official IBKR TWS Python API.

    The official ``ibapi`` package is imported lazily because IBKR distributes
    the Python API with the TWS API download. Offline tests therefore remain
    independent of a local TWS installation.
    """

    ACCOUNT_TAGS = (
        "NetLiquidation,TotalCashValue,AvailableFunds,BuyingPower,"
        "ExcessLiquidity,Currency"
    )

    def __init__(self) -> None:
        self._config: IbkrPaperConnectionConfig | None = None
        self._app: Any | None = None
        self._thread: threading.Thread | None = None
        self._request_id = 9000

    def connect(self, config: IbkrPaperConnectionConfig) -> IbkrConnectionStatus:
        config.validate()
        if not config.read_only:
            raise ValueError("IBKR connectivity verification requires read_only=true")

        app_class = self._build_app_class()
        app = app_class()
        app.connect(config.host, config.port, clientId=config.client_id)
        thread = threading.Thread(target=app.run, name="ibkr-tws-api", daemon=True)
        thread.start()

        if not app.api_ready.wait(config.timeout_seconds):
            app.disconnect()
            raise TimeoutError(
                f"IBKR API did not become ready within {config.timeout_seconds:.1f}s"
            )
        # managedAccounts normally arrives during connection establishment. If
        # delayed, explicitly request it and wait for the same bounded window.
        if not app.accounts_ready.is_set():
            app.reqManagedAccts()
        if not app.accounts_ready.wait(config.timeout_seconds):
            app.disconnect()
            raise TimeoutError("IBKR managed-account discovery timed out")
        if app.fatal_error:
            message = app.fatal_error
            app.disconnect()
            raise RuntimeError(message)

        accounts = tuple(sorted({value.upper() for value in app.managed_accounts}))
        if not accounts:
            app.disconnect()
            raise RuntimeError("IBKR session returned no managed accounts")
        if config.expected_account_id.upper() not in accounts:
            app.disconnect()
            raise RuntimeError("Connected IBKR session does not expose the registered account")
        if any(not account.startswith("DU") for account in accounts):
            app.disconnect()
            raise RuntimeError("Paper-only safeguard rejected a non-DU managed account")

        self._config = config
        self._app = app
        self._thread = thread
        return IbkrConnectionStatus(
            connected=True,
            environment="PAPER",
            account_ids=accounts,
            server_version=app.serverVersion(),
            message="CONNECTED_READ_ONLY",
        )

    def disconnect(self) -> None:
        app = self._app
        self._app = None
        self._config = None
        if app is not None:
            try:
                app.disconnect()
            finally:
                if self._thread and self._thread.is_alive():
                    self._thread.join(timeout=2.0)
        self._thread = None

    def account_summary(self, account_id: str) -> IbkrAccountSummary:
        app, config = self._require_connection()
        request_id = self._next_request_id()
        app.begin_account_summary(request_id)
        app.reqAccountSummary(request_id, "All", self.ACCOUNT_TAGS)
        if not app.account_summary_ready.wait(config.timeout_seconds):
            app.cancelAccountSummary(request_id)
            raise TimeoutError("IBKR account-summary request timed out")
        app.cancelAccountSummary(request_id)
        if app.request_error:
            raise RuntimeError(app.request_error)

        account_id = account_id.upper()
        values = app.account_values.get(account_id, {})
        if not values:
            raise RuntimeError(f"IBKR returned no account summary for {account_id}")

        currency = values.get("Currency", {}).get("value", "") or "USD"
        raw = {tag: dict(payload) for tag, payload in values.items()}
        return IbkrAccountSummary(
            broker_account_id=account_id,
            base_currency=currency,
            net_liquidation=self._number(values, "NetLiquidation"),
            total_cash_value=self._number(values, "TotalCashValue"),
            available_funds=self._number(values, "AvailableFunds"),
            buying_power=self._number(values, "BuyingPower"),
            excess_liquidity=self._number(values, "ExcessLiquidity"),
            captured_at=utc_now_iso(),
            raw=raw,
        )

    def positions(self, account_id: str) -> list[IbkrPositionSnapshot]:
        app, config = self._require_connection()
        app.begin_positions()
        app.reqPositions()
        if not app.positions_ready.wait(config.timeout_seconds):
            app.cancelPositions()
            raise TimeoutError("IBKR positions request timed out")
        app.cancelPositions()
        if app.request_error:
            raise RuntimeError(app.request_error)

        account_id = account_id.upper()
        captured_at = utc_now_iso()
        rows: list[IbkrPositionSnapshot] = []
        for item in app.position_rows:
            if item["account"].upper() != account_id:
                continue
            contract = item["contract"]
            multiplier = self._float(getattr(contract, "multiplier", "") or 1.0)
            rows.append(
                IbkrPositionSnapshot(
                    broker_account_id=account_id,
                    contract_id=int(getattr(contract, "conId", 0) or 0),
                    symbol=str(getattr(contract, "symbol", "") or ""),
                    local_symbol=str(getattr(contract, "localSymbol", "") or ""),
                    security_type=str(getattr(contract, "secType", "") or ""),
                    currency=str(getattr(contract, "currency", "") or "USD"),
                    exchange=str(
                        getattr(contract, "primaryExchange", "")
                        or getattr(contract, "exchange", "")
                        or "SMART"
                    ),
                    quantity=self._float(item["position"]),
                    average_cost=self._float(item["average_cost"]),
                    expiry=str(getattr(contract, "lastTradeDateOrContractMonth", "") or ""),
                    strike=self._optional_float(getattr(contract, "strike", None)),
                    right=str(getattr(contract, "right", "") or ""),
                    multiplier=multiplier,
                    captured_at=captured_at,
                    raw={
                        "account": account_id,
                        "contract": {
                            "conId": int(getattr(contract, "conId", 0) or 0),
                            "symbol": str(getattr(contract, "symbol", "") or ""),
                            "localSymbol": str(getattr(contract, "localSymbol", "") or ""),
                            "secType": str(getattr(contract, "secType", "") or ""),
                            "currency": str(getattr(contract, "currency", "") or ""),
                            "exchange": str(getattr(contract, "exchange", "") or ""),
                            "primaryExchange": str(getattr(contract, "primaryExchange", "") or ""),
                            "expiry": str(getattr(contract, "lastTradeDateOrContractMonth", "") or ""),
                            "strike": self._optional_float(getattr(contract, "strike", None)),
                            "right": str(getattr(contract, "right", "") or ""),
                            "multiplier": multiplier,
                        },
                        "position": self._float(item["position"]),
                        "average_cost": self._float(item["average_cost"]),
                    },
                )
            )
        return rows

    def health(self) -> dict[str, Any]:
        app, _ = self._require_connection()
        return {
            "connected": bool(app.isConnected()),
            "server_version": app.serverVersion(),
            "managed_accounts": tuple(sorted(app.managed_accounts)),
            "message": "CONNECTED_READ_ONLY",
        }

    def _require_connection(self):
        if self._app is None or self._config is None or not self._app.isConnected():
            raise RuntimeError("IBKR transport is not connected")
        return self._app, self._config

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    @classmethod
    def _number(cls, values: dict, tag: str) -> float:
        payload = values.get(tag, {})
        return cls._float(payload.get("value", 0.0))

    @staticmethod
    def _float(value: Any) -> float:
        if isinstance(value, Decimal):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _optional_float(cls, value: Any) -> float | None:
        if value in (None, ""):
            return None
        result = cls._float(value)
        return result if result != 0.0 else None

    @staticmethod
    def _build_app_class():
        try:
            from ibapi.client import EClient
            from ibapi.wrapper import EWrapper
        except ImportError as exc:
            raise RuntimeError(
                "The official IBKR TWS Python API is not installed. Install it from the "
                "IBKR TWS API download, then rerun this command."
            ) from exc

        class _IbkrReadOnlyApp(EWrapper, EClient):
            def __init__(self) -> None:
                EClient.__init__(self, self)
                self.api_ready = threading.Event()
                self.accounts_ready = threading.Event()
                self.account_summary_ready = threading.Event()
                self.positions_ready = threading.Event()
                self.managed_accounts: set[str] = set()
                self.account_values: dict[str, dict[str, dict[str, str]]] = {}
                self.position_rows: list[dict[str, Any]] = []
                self.active_account_request_id: int | None = None
                self.request_error = ""
                self.fatal_error = ""

            def nextValidId(self, orderId: int) -> None:  # noqa: N802
                self.api_ready.set()

            def managedAccounts(self, accountsList: str) -> None:  # noqa: N802
                self.managed_accounts = {
                    value.strip().upper()
                    for value in accountsList.split(",")
                    if value.strip()
                }
                self.accounts_ready.set()

            def begin_account_summary(self, request_id: int) -> None:
                self.active_account_request_id = request_id
                self.request_error = ""
                self.account_values = {}
                self.account_summary_ready.clear()

            def accountSummary(  # noqa: N802
                self,
                reqId: int,
                account: str,
                tag: str,
                value: str,
                currency: str,
            ) -> None:
                if reqId != self.active_account_request_id:
                    return
                self.account_values.setdefault(account.upper(), {})[tag] = {
                    "value": value,
                    "currency": currency,
                }

            def accountSummaryEnd(self, reqId: int) -> None:  # noqa: N802
                if reqId == self.active_account_request_id:
                    self.account_summary_ready.set()

            def begin_positions(self) -> None:
                self.request_error = ""
                self.position_rows = []
                self.positions_ready.clear()

            def position(self, account, contract, position, avgCost) -> None:
                self.position_rows.append(
                    {
                        "account": account,
                        "contract": contract,
                        "position": position,
                        "average_cost": avgCost,
                    }
                )

            def positionEnd(self) -> None:  # noqa: N802
                self.positions_ready.set()

            def error(self, reqId, errorCode, errorString, advancedOrderRejectJson="") -> None:
                # Informational connectivity notices are not request failures.
                if errorCode in {2104, 2106, 2107, 2108, 2158}:
                    return
                message = f"IBKR error {errorCode}: {errorString}"
                if errorCode in {502, 503, 504, 1100, 1300}:
                    self.fatal_error = message
                    self.api_ready.set()
                    self.accounts_ready.set()
                elif reqId and reqId > 0:
                    self.request_error = message
                    self.account_summary_ready.set()
                    self.positions_ready.set()

            def connectionClosed(self) -> None:  # noqa: N802
                if not self.fatal_error:
                    self.fatal_error = "IBKR connection closed"

        return _IbkrReadOnlyApp
