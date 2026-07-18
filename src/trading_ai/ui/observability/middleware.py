from __future__ import annotations

import time
from uuid import uuid4

from fastapi import Request

from trading_ai.ui.observability.metrics_registry import MetricsRegistry
from trading_ai.ui.observability.structured_logging import StructuredLogManager


class ObservabilityMiddleware:
    def __init__(self, app):
        self.app = app
        self.metrics = MetricsRegistry.shared()
        self.logs = StructuredLogManager()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        correlation_id = request.headers.get(
            "x-correlation-id",
            f"corr-{uuid4().hex}",
        )
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append(
                    (b"x-correlation-id", correlation_id.encode("utf-8"))
                )
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            outcome = "SUCCESS" if status_code < 500 else "ERROR"
        except Exception:
            outcome = "EXCEPTION"
            self.metrics.increment(
                "http_requests_total",
                labels={
                    "method": request.method,
                    "path": request.url.path,
                    "status": "500",
                },
            )
            self.logs.emit(
                level=40,
                message="Unhandled workstation request exception",
                event_type="HTTP_REQUEST",
                component="workstation_api",
                operation=request.url.path,
                outcome=outcome,
                correlation_id=correlation_id,
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            self.metrics.increment(
                "http_requests_total",
                labels={
                    "method": request.method,
                    "path": request.url.path,
                    "status": str(status_code),
                },
            )
            self.metrics.gauge(
                "http_request_duration_ms",
                duration_ms,
                labels={
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            self.logs.emit(
                message="Workstation HTTP request completed",
                event_type="HTTP_REQUEST",
                component="workstation_api",
                operation=request.url.path,
                outcome=outcome,
                duration_ms=round(duration_ms, 3),
                correlation_id=correlation_id,
            )
