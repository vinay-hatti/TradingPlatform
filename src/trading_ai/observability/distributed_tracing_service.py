from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .observability_policy import DistributedTracingPolicy
from .observability_profile import (
    SpanEvent,
    TraceRecord,
    TraceSpan,
)


class DistributedTracingService:
    def __init__(
        self,
        *,
        policy: DistributedTracingPolicy | None = None,
        path: str | Path = (
            "data/observability/traces.json"
        ),
    ) -> None:
        self.policy = policy or DistributedTracingPolicy()
        self.policy.validate()
        self.path = Path(path)
        self._active: dict[str, TraceSpan] = {}
        self._completed: list[TraceSpan] = []
        self._traces: list[TraceRecord] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self._traces = []
        for raw in payload.get("traces", []):
            spans = tuple(
                TraceSpan(
                    **{
                        **span,
                        "events": tuple(
                            SpanEvent(**event)
                            for event in span.get("events", ())
                        ),
                    }
                )
                for span in raw.get("spans", ())
            )
            self._traces.append(
                TraceRecord(**{**raw, "spans": spans})
            )

    @staticmethod
    def _identifier(prefix: str, raw: str) -> str:
        return hashlib.sha256(
            f"{prefix}:{raw}".encode("utf-8")
        ).hexdigest()[:32]

    def _sampled(self, trace_id: str) -> bool:
        bucket = int(trace_id[:8], 16) / 0xFFFFFFFF
        return bucket <= self.policy.sampling_rate

    def start_span(
        self,
        *,
        name: str,
        service_name: str,
        environment: str,
        parent: TraceSpan | None = None,
        kind: str = "INTERNAL",
        attributes: dict[str, Any] | None = None,
        baggage: dict[str, str] | None = None,
    ) -> TraceSpan:
        now = datetime.now(timezone.utc).isoformat()
        trace_id = (
            parent.trace_id
            if parent is not None
            else self._identifier(
                "trace",
                f"{service_name}:{name}:{now}",
            )
        )
        span_id = self._identifier(
            "span",
            f"{trace_id}:{name}:{now}:{len(self._active)}",
        )[:16]
        attributes = attributes or {}
        if len(attributes) > self.policy.maximum_span_attributes:
            raise ValueError("Span attribute count exceeds policy")
        cleaned = {
            key: str(value)[: self.policy.maximum_attribute_value_length]
            for key, value in attributes.items()
        }
        combined_baggage = {}
        if self.policy.propagate_baggage and parent is not None:
            combined_baggage.update(parent.baggage)
        combined_baggage.update(baggage or {})
        span = TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            service_name=service_name,
            environment=environment,
            parent_span_id=parent.span_id if parent else None,
            kind=kind,
            sampled=self._sampled(trace_id),
            start_time=now,
            attributes=cleaned,
            baggage=combined_baggage,
        )
        self._active[span.span_id] = span
        return span

    def add_event(
        self,
        span: TraceSpan,
        *,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> TraceSpan:
        current = self._active.get(span.span_id, span)
        if len(current.events) >= self.policy.maximum_span_events:
            raise ValueError("Span event count exceeds policy")
        event = SpanEvent(name=name, attributes=attributes or {})
        updated = replace(
            current,
            events=current.events + (event,),
        )
        self._active[span.span_id] = updated
        return updated

    def end_span(
        self,
        span: TraceSpan,
        *,
        status: str = "OK",
        error: BaseException | None = None,
    ) -> TraceSpan:
        current = self._active.pop(span.span_id, span)
        completed = replace(
            current,
            status="ERROR" if error else status,
            end_time=datetime.now(timezone.utc).isoformat(),
            error_type=type(error).__name__ if error else None,
            error_message=str(error) if error else None,
        )
        self._completed.append(completed)
        self._finalize_trace_if_complete(completed.trace_id)
        return completed

    def _finalize_trace_if_complete(self, trace_id: str) -> None:
        if any(
            span.trace_id == trace_id
            for span in self._active.values()
        ):
            return
        spans = tuple(
            span for span in self._completed
            if span.trace_id == trace_id
        )
        if not spans:
            return
        root = next(
            (span for span in spans if span.parent_span_id is None),
            spans[0],
        )
        record = TraceRecord(
            trace_id=trace_id,
            root_span_id=root.span_id,
            service_name=root.service_name,
            environment=root.environment,
            spans=spans,
            started_at=min(span.start_time for span in spans),
            completed_at=max(
                span.end_time or span.start_time for span in spans
            ),
            status=(
                "ERROR"
                if any(span.status == "ERROR" for span in spans)
                else "OK"
            ),
        )
        self._traces.append(record)
        self._completed = [
            span for span in self._completed
            if span.trace_id != trace_id
        ]
        self._persist()

    def _persist(self) -> None:
        if not self.policy.persist_completed_traces:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(
                {
                    "traces": [
                        record.to_dict() for record in self._traces
                    ]
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)

    def traces(self) -> tuple[TraceRecord, ...]:
        return tuple(self._traces)
