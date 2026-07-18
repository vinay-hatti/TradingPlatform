from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.models.execution_console import (
    CancelOrderRequest,
    ExecutionAlert,
    ExecutionConsoleResponse,
    ExecutionFill,
    ExecutionOrder,
    ExecutionQuality,
    OrderCommandResult,
    ReplaceOrderRequest,
)


def val(row: Any, *names: str, default=None):
    for name in names:
        candidate = row.get(name) if isinstance(row, dict) else getattr(row, name, None)
        if candidate not in (None, ""):
            return candidate
    return default


def num(raw, default=None):
    try:
        if raw in (None, ""):
            return default
        return float(str(raw).replace("$", "").replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return default


def parse_datetime(raw):
    if raw in (None, ""):
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def file_time(path: Path):
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


class ExecutionCommandService(Protocol):
    def cancel_order(self, order_id: str, reason: str) -> Any: ...
    def replace_order(
        self,
        order_id: str,
        quantity: float | None,
        limit_price: float | None,
        stop_price: float | None,
        reason: str,
    ) -> Any: ...


class ExecutionConsoleService:
    ORDER_PATTERNS = (
        "execution/**/*.json",
        "execution/**/*.csv",
        "broker/**/*.json",
        "broker/**/*.csv",
        "paper_trading/**/*order*.json",
        "paper_trading/**/*order*.csv",
        "**/orders*.json",
        "**/orders*.csv",
        "**/broker_order*.json",
        "**/broker_order*.csv",
    )
    FILL_PATTERNS = (
        "execution/**/*fill*.json",
        "execution/**/*fill*.csv",
        "broker/**/*fill*.json",
        "broker/**/*fill*.csv",
        "paper_trading/**/*fill*.json",
        "paper_trading/**/*fill*.csv",
        "**/fills*.json",
        "**/fills*.csv",
    )
    METRIC_PATTERNS = (
        "execution/**/*metric*.json",
        "execution/**/*quality*.json",
        "execution/**/*reconciliation*.json",
        "**/execution_analytics*.json",
        "**/execution_quality*.json",
        "**/broker_reconciliation*.json",
    )

    TERMINAL = {"FILLED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED"}
    OPEN = {"NEW", "PENDING", "SUBMITTED", "ACCEPTED", "OPEN", "PARTIALLY_FILLED", "REPLACED"}

    def __init__(
        self,
        artifacts: RepositoryArtifactAdapters | None = None,
        commands: ExecutionCommandService | None = None,
        stale_after_seconds: int = 900,
        stale_order_seconds: int = 1800,
    ):
        self.artifacts = artifacts or RepositoryArtifactAdapters()
        self.commands = commands
        self.stale_after_seconds = stale_after_seconds
        self.stale_order_seconds = stale_order_seconds

    @property
    def reports_root(self):
        return self.artifacts.root / "reports"

    def _files(self, patterns):
        found = {}
        for pattern in patterns:
            for path in self.reports_root.glob(pattern):
                if path.is_file():
                    found[str(path.resolve())] = path
        return sorted(found.values(), key=lambda p: p.stat().st_mtime, reverse=True)

    @staticmethod
    def _read(path):
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _extract(payload, keys):
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in keys:
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    return [item for item in candidate if isinstance(item, dict)]
            if any(key in payload for key in ("order_id", "id", "fill_id", "execution_id")):
                return [payload]
        return []

    def _order(self, row, path):
        order_id = str(val(row, "order_id", "broker_order_id", "id", default="")).strip()
        symbol = str(val(row, "symbol", "ticker", "underlying_symbol", default="")).strip().upper()
        if not order_id or not symbol:
            return None

        quantity = num(val(row, "quantity", "qty", "requested_quantity", default=0), 0.0) or 0.0
        filled = num(val(row, "filled_quantity", "filled_qty", "executed_quantity", default=0), 0.0) or 0.0
        remaining = num(val(row, "remaining_quantity", "remaining_qty"))
        if remaining is None:
            remaining = max(quantity - filled, 0.0)

        status = str(val(row, "status", "order_status", "state", default="UNKNOWN")).upper()
        return ExecutionOrder(
            order_id=order_id,
            client_order_id=str(val(row, "client_order_id", "idempotency_key", default="")) or None,
            symbol=symbol,
            contract=str(val(row, "contract", "option_symbol", "instrument", default="")) or None,
            strategy=str(val(row, "strategy", "strategy_name", default="Unknown")),
            side=str(val(row, "side", "action", "direction", default="UNKNOWN")).upper(),
            order_type=str(val(row, "order_type", "type", default="UNKNOWN")).upper(),
            time_in_force=str(val(row, "time_in_force", "tif", default="")) or None,
            quantity=quantity,
            filled_quantity=filled,
            remaining_quantity=remaining,
            limit_price=num(val(row, "limit_price", "price")),
            stop_price=num(val(row, "stop_price")),
            average_fill_price=num(val(row, "average_fill_price", "avg_fill_price", "filled_price")),
            status=status,
            broker_status=str(val(row, "broker_status", "external_status", default="")) or None,
            submitted_at=parse_datetime(val(row, "submitted_at", "created_at", "order_time")),
            updated_at=parse_datetime(val(row, "updated_at", "last_update_at", "status_time")) or file_time(path),
            source=str(path.relative_to(self.reports_root)),
            can_cancel=self.commands is not None and status in self.OPEN,
            can_replace=self.commands is not None and status in self.OPEN,
        )

    def _fill(self, row, path):
        fill_id = str(val(row, "fill_id", "execution_id", "id", default="")).strip()
        order_id = str(val(row, "order_id", "broker_order_id", default="")).strip()
        symbol = str(val(row, "symbol", "ticker", "underlying_symbol", default="")).strip().upper()
        price = num(val(row, "price", "fill_price", "execution_price"))
        quantity = num(val(row, "quantity", "fill_quantity", "filled_qty"))
        if not fill_id or not order_id or not symbol or price is None or quantity is None:
            return None
        return ExecutionFill(
            fill_id=fill_id,
            order_id=order_id,
            symbol=symbol,
            quantity=quantity,
            price=price,
            commission=num(val(row, "commission", "fee", "fees"), 0.0) or 0.0,
            liquidity=str(val(row, "liquidity", "liquidity_flag", default="")) or None,
            venue=str(val(row, "venue", "exchange", default="")) or None,
            filled_at=parse_datetime(val(row, "filled_at", "execution_time", "timestamp")) or file_time(path),
            source=str(path.relative_to(self.reports_root)),
        )

    def _load(self, patterns, keys, mapper):
        items, selected = [], []
        for path in self._files(patterns)[:50]:
            try:
                rows = self._extract(self._read(path), keys)
            except Exception:
                continue
            mapped = [item for item in (mapper(row, path) for row in rows) if item is not None]
            if mapped:
                items.extend(mapped)
                selected.append(path)
        return items, selected

    def _metrics_payload(self):
        for path in self._files(self.METRIC_PATTERNS):
            try:
                payload = self._read(path)
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload, path
        return {}, None

    def get(self):
        orders, order_paths = self._load(
            self.ORDER_PATTERNS,
            ("orders", "open_orders", "order_history", "items", "data"),
            self._order,
        )
        fills, fill_paths = self._load(
            self.FILL_PATTERNS,
            ("fills", "executions", "fill_history", "items", "data"),
            self._fill,
        )
        metrics, metric_path = self._metrics_payload()

        # Deduplicate by latest order update.
        by_order = {}
        for order in sorted(orders, key=lambda x: x.updated_at or datetime.min.replace(tzinfo=timezone.utc)):
            by_order[order.order_id] = order
        orders = sorted(
            by_order.values(),
            key=lambda x: x.updated_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        now = datetime.now(timezone.utc)
        alerts = []
        reconciliation_breaks = int(num(val(metrics, "reconciliation_breaks", "break_count"), 0) or 0)
        stale_orders = 0
        for order in orders:
            if order.status in self.OPEN and order.updated_at:
                age = (now - order.updated_at).total_seconds()
                if age > self.stale_order_seconds:
                    stale_orders += 1
                    alerts.append(ExecutionAlert(
                        severity="WARNING",
                        code="STALE_ORDER",
                        message=f"Order has not changed for {int(age)} seconds.",
                        order_id=order.order_id,
                        detected_at=now,
                    ))
            if order.status == "REJECTED":
                alerts.append(ExecutionAlert(
                    severity="CRITICAL",
                    code="ORDER_REJECTED",
                    message=f"Broker rejected {order.symbol} order.",
                    order_id=order.order_id,
                    detected_at=now,
                ))

        if reconciliation_breaks:
            alerts.append(ExecutionAlert(
                severity="CRITICAL",
                code="RECONCILIATION_BREAK",
                message=f"{reconciliation_breaks} broker reconciliation breaks detected.",
                detected_at=now,
            ))

        submitted = len(orders)
        filled_count = sum(1 for x in orders if x.status == "FILLED")
        open_count = sum(1 for x in orders if x.status in self.OPEN)
        cancelled = sum(1 for x in orders if x.status in {"CANCELLED", "CANCELED"})
        rejected = sum(1 for x in orders if x.status == "REJECTED")

        fill_rate = num(val(metrics, "fill_rate_pct", "fill_rate"))
        if fill_rate is None and submitted:
            fill_rate = filled_count / submitted * 100.0

        quality = ExecutionQuality(
            submitted_orders=submitted,
            open_orders=open_count,
            filled_orders=filled_count,
            cancelled_orders=cancelled,
            rejected_orders=rejected,
            fill_rate_pct=fill_rate,
            average_fill_latency_ms=num(val(metrics, "average_fill_latency_ms", "avg_fill_latency_ms")),
            average_slippage_bps=num(val(metrics, "average_slippage_bps", "avg_slippage_bps")),
            total_slippage=num(val(metrics, "total_slippage", "slippage_cost")),
            total_commission=sum(fill.commission for fill in fills),
            reconciliation_breaks=reconciliation_breaks,
            stale_orders=stale_orders,
        )

        paths = order_paths + fill_paths + ([metric_path] if metric_path else [])
        latest = max((file_time(path) for path in paths), default=None)
        age = max(0.0, (now - latest).total_seconds()) if latest else None
        notices = []
        if not orders:
            notices.append("No execution order artifacts were found.")
        if not fills:
            notices.append("No execution fill artifacts were found.")
        if self.commands is None:
            notices.append("Order actions are read-only because no governed execution command service is configured.")

        return ExecutionConsoleResponse(
            generated_at=now,
            available=bool(orders or fills or metrics),
            stale=age is None or age > self.stale_after_seconds,
            age_seconds=round(age, 2) if age is not None else None,
            command_mode="GOVERNED_WRITE" if self.commands else "READ_ONLY",
            source_detail="; ".join(str(p.relative_to(self.reports_root)) for p in paths[:8]) or "No execution artifacts available.",
            quality=quality,
            orders=orders,
            fills=sorted(fills, key=lambda x: x.filled_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True),
            alerts=alerts,
            notices=notices,
        )

    def cancel(self, order_id: str, request: CancelOrderRequest):
        now = datetime.now(timezone.utc)
        if self.commands is None:
            return OrderCommandResult(
                accepted=False,
                order_id=order_id,
                action="CANCEL",
                message="Execution console is read-only; governed command service is not configured.",
                requested_at=now,
            )
        result = self.commands.cancel_order(order_id, request.reason)
        return OrderCommandResult(
            accepted=True,
            order_id=order_id,
            action="CANCEL",
            message=str(result),
            requested_at=now,
        )

    def replace(self, order_id: str, request: ReplaceOrderRequest):
        now = datetime.now(timezone.utc)
        if self.commands is None:
            return OrderCommandResult(
                accepted=False,
                order_id=order_id,
                action="REPLACE",
                message="Execution console is read-only; governed command service is not configured.",
                requested_at=now,
            )
        result = self.commands.replace_order(
            order_id,
            request.quantity,
            request.limit_price,
            request.stop_price,
            request.reason,
        )
        return OrderCommandResult(
            accepted=True,
            order_id=order_id,
            action="REPLACE",
            message=str(result),
            requested_at=now,
        )
