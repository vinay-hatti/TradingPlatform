from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .instrumentation_policy import TracePropagationPolicy
from .observability_profile import ObservabilityContext, TraceSpan


_TRACEPARENT = re.compile(
    r"^(?P<version>[0-9a-f]{2})-"
    r"(?P<trace_id>[0-9a-f]{32})-"
    r"(?P<span_id>[0-9a-f]{16})-"
    r"(?P<flags>[0-9a-f]{2})$"
)


@dataclass(frozen=True)
class ExtractedTraceContext:
    trace_id: str | None
    parent_span_id: str | None
    sampled: bool
    baggage: dict[str, str]
    correlation_id: str | None
    request_id: str | None


class TracePropagationService:
    def __init__(
        self,
        policy: TracePropagationPolicy | None = None,
    ) -> None:
        self.policy = policy or TracePropagationPolicy()
        self.policy.validate()

    def inject(
        self,
        *,
        span: TraceSpan,
        context: ObservabilityContext | None = None,
    ) -> dict[str, str]:
        flags = "01" if span.sampled else "00"
        headers = {
            self.policy.trace_header: (
                f"00-{span.trace_id}-{span.span_id}-{flags}"
            )
        }
        if self.policy.propagate_baggage and span.baggage:
            headers[self.policy.baggage_header] = ",".join(
                f"{key}={value}"
                for key, value in sorted(span.baggage.items())
            )
        if context and context.correlation_id:
            headers[self.policy.correlation_header] = (
                context.correlation_id
            )
        if context and context.request_id:
            headers[self.policy.request_header] = context.request_id
        return headers

    def extract(
        self,
        headers: Mapping[str, str],
    ) -> ExtractedTraceContext:
        normalized = {
            str(key).lower(): str(value)
            for key, value in headers.items()
        }
        raw = normalized.get(self.policy.trace_header.lower())
        trace_id = None
        span_id = None
        sampled = False
        if raw:
            match = _TRACEPARENT.match(raw.strip().lower())
            if not match:
                if self.policy.require_valid_traceparent:
                    raise ValueError("Invalid traceparent header")
            else:
                trace_id = match.group("trace_id")
                span_id = match.group("span_id")
                sampled = (
                    int(match.group("flags"), 16) & 0x01
                ) == 0x01

        baggage: dict[str, str] = {}
        if self.policy.propagate_baggage:
            raw_baggage = normalized.get(
                self.policy.baggage_header.lower(), ""
            )
            for item in raw_baggage.split(","):
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                baggage[key.strip()] = value.strip()

        return ExtractedTraceContext(
            trace_id=trace_id,
            parent_span_id=span_id,
            sampled=sampled,
            baggage=baggage,
            correlation_id=normalized.get(
                self.policy.correlation_header.lower()
            ),
            request_id=normalized.get(
                self.policy.request_header.lower()
            ),
        )
