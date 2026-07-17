from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Mapping

from .realtime_event_dispatcher import RealTimeMarketEventDispatcher
from .realtime_market_data_profile import RawQuoteEvent, RawTradeEvent
from .realtime_market_data_service import RealTimeMarketDataService
from .realtime_pipeline_policy import RealTimePipelinePolicy
from .realtime_pipeline_profile import (
    DispatchedMarketEvent,
    PaperStreamEventProfile,
    PipelineHealthProfile,
)
from .realtime_provider_adapter import RealTimeMarketDataProviderAdapter


class NormalizedMarketDataPipeline:
    def __init__(
        self,
        *,
        market_data_service: RealTimeMarketDataService | None = None,
        dispatcher: RealTimeMarketEventDispatcher | None = None,
        policy: RealTimePipelinePolicy | None = None,
    ) -> None:
        self.market_data_service = market_data_service or RealTimeMarketDataService()
        self.dispatcher = dispatcher or RealTimeMarketEventDispatcher()
        self.policy = policy or RealTimePipelinePolicy()
        self.policy.validate()
        self._queue: deque[PaperStreamEventProfile | Mapping[str, Any] | Any] = deque()
        self._rejected: deque[DispatchedMarketEvent] = deque(
            maxlen=self.policy.maximum_rejected_events or None
        )
        self._last_sequence_by_provider: dict[str, int] = {}
        self._last_timestamp_by_symbol_type: dict[tuple[str, str], str] = {}
        self._received_count = 0
        self._accepted_count = 0
        self._rejected_count = 0
        self._quote_count = 0
        self._trade_count = 0
        self._dispatch_error_count = 0
        self._sequence_gap_count = 0
        self._out_of_order_count = 0
        self._last_event_at: str | None = None
        self._state = "IDLE"

    @staticmethod
    def _value(obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, Mapping):
            return obj.get(name, default)
        return getattr(obj, name, default)

    def bind_adapter(self, adapter: RealTimeMarketDataProviderAdapter) -> None:
        adapter.set_event_callback(self.enqueue)
        adapter.set_lifecycle_callback(self._on_lifecycle)

    def _on_lifecycle(self, event: str, metadata: dict[str, Any]) -> None:
        normalized = event.strip().upper()
        if normalized == "CONNECTED":
            self._state = "RUNNING"
        elif normalized in {"DISCONNECTED", "FAILED"}:
            self._state = "DEGRADED"
        elif normalized == "STOPPED":
            self._state = "STOPPED"

    def enqueue(self, event: Any) -> bool:
        if len(self._queue) >= self.policy.maximum_queue_size:
            if self.policy.reject_when_queue_full:
                return False
            self._queue.popleft()
        self._queue.append(event)
        return True

    def pending_count(self) -> int:
        return len(self._queue)

    def rejected_events(self) -> tuple[DispatchedMarketEvent, ...]:
        return tuple(self._rejected)

    def process_next(self) -> DispatchedMarketEvent | None:
        if not self._queue:
            return None
        event = self._queue.popleft()
        return self.process_event(event)

    def process_all(self) -> tuple[DispatchedMarketEvent, ...]:
        results: list[DispatchedMarketEvent] = []
        while self._queue:
            result = self.process_next()
            if result is not None:
                results.append(result)
        return tuple(results)

    def _sequence_checks(
        self,
        provider: str,
        sequence_number: int | None,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        warnings: list[str] = []
        rejections: list[str] = []
        if sequence_number is None:
            return tuple(warnings), tuple(rejections)

        previous = self._last_sequence_by_provider.get(provider)
        if previous is not None:
            if sequence_number <= previous:
                self._out_of_order_count += 1
                if self.policy.require_monotonic_sequence:
                    rejections.append("NON_MONOTONIC_SEQUENCE")
                else:
                    warnings.append("NON_MONOTONIC_SEQUENCE")
            elif sequence_number - previous > self.policy.maximum_sequence_gap:
                self._sequence_gap_count += 1
                warnings.append("SEQUENCE_GAP")
        if previous is None or sequence_number > previous:
            self._last_sequence_by_provider[provider] = sequence_number
        return tuple(warnings), tuple(rejections)

    def process_event(self, event: Any) -> DispatchedMarketEvent:
        self._state = "RUNNING"
        self._received_count += 1
        self._last_event_at = datetime.now(timezone.utc).isoformat()

        event_type = str(self._value(event, "event_type", "")).strip().upper()
        symbol = str(self._value(event, "symbol", "")).strip().upper()
        provider = str(self._value(event, "provider", "unknown")).strip().lower()
        sequence_number = self._value(event, "sequence_number", None)
        payload = self._value(event, "payload", event)

        sequence_warnings, sequence_rejections = self._sequence_checks(
            provider,
            sequence_number,
        )

        previous_timestamp = self._last_timestamp_by_symbol_type.get(
            (symbol, event_type)
        )

        normalized_payload = None
        quality = None
        warnings = list(sequence_warnings)
        rejections = list(sequence_rejections)

        if event_type == "QUOTE":
            raw = dict(payload) if isinstance(payload, Mapping) else payload
            if isinstance(raw, dict):
                raw.setdefault("symbol", symbol)
                raw.setdefault("source", {
                    "provider": provider,
                    "sequence_number": sequence_number,
                })
            result = self.market_data_service.process_quote(
                raw,
                previous_exchange_timestamp=previous_timestamp,
            )
            normalized_payload = result.quote
            quality = result.quality
            warnings.extend(result.warnings)
            rejections.extend(result.rejection_reasons)
            self._quote_count += 1
            if result.quote is not None:
                self._last_timestamp_by_symbol_type[(symbol, event_type)] = (
                    result.quote.exchange_timestamp
                )
        elif event_type == "TRADE":
            raw = dict(payload) if isinstance(payload, Mapping) else payload
            if isinstance(raw, dict):
                raw.setdefault("symbol", symbol)
                raw.setdefault("source", {
                    "provider": provider,
                    "sequence_number": sequence_number,
                })
            result = self.market_data_service.process_trade(
                raw,
                previous_exchange_timestamp=previous_timestamp,
            )
            normalized_payload = result.trade
            quality = result.quality
            warnings.extend(result.warnings)
            rejections.extend(result.rejection_reasons)
            self._trade_count += 1
            if result.trade is not None:
                self._last_timestamp_by_symbol_type[(symbol, event_type)] = (
                    result.trade.exchange_timestamp
                )
        else:
            rejections.append("UNSUPPORTED_EVENT_TYPE")

        accepted = not rejections and bool(
            getattr(quality, "allowed", False)
        )
        dispatched = DispatchedMarketEvent(
            event_id=uuid.uuid4().hex,
            event_type=event_type or "UNKNOWN",
            symbol=symbol,
            provider=provider,
            sequence_number=sequence_number,
            received_at=self._last_event_at,
            accepted=accepted,
            payload=normalized_payload,
            quality=quality,
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            metadata={"pipeline_state": self._state},
        )

        if accepted:
            self._accepted_count += 1
            errors = self.dispatcher.dispatch(dispatched)
            if errors:
                self._dispatch_error_count += len(errors)
                if self.policy.stop_on_dispatch_error:
                    self._state = "FAILED"
        else:
            self._rejected_count += 1
            if self.policy.retain_rejected_events:
                self._rejected.append(dispatched)

        return dispatched

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def health(self) -> PipelineHealthProfile:
        rejection_rate = (
            self._rejected_count / self._received_count
            if self._received_count else 0.0
        )
        dispatch_error_rate = (
            self._dispatch_error_count / max(self._accepted_count, 1)
        )
        score = max(
            0.0,
            100.0
            - rejection_rate * 60.0
            - dispatch_error_rate * 25.0
            - min(self._sequence_gap_count, 5) * 2.0
            - min(self._out_of_order_count, 5) * 3.0,
        )
        grade, severity = self._grade(score)
        rejections: list[str] = []
        if score < self.policy.minimum_pipeline_score:
            rejections.append("PIPELINE_SCORE_BELOW_MINIMUM")
        if self._state == "FAILED":
            rejections.append("PIPELINE_FAILED")
        allowed = not rejections
        return PipelineHealthProfile(
            valid=True,
            allowed=allowed,
            state=self._state,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="CONTINUE" if allowed else "STOP",
            received_count=self._received_count,
            accepted_count=self._accepted_count,
            rejected_count=self._rejected_count,
            quote_count=self._quote_count,
            trade_count=self._trade_count,
            dispatch_error_count=self._dispatch_error_count,
            sequence_gap_count=self._sequence_gap_count,
            out_of_order_count=self._out_of_order_count,
            subscriber_count=len(self.dispatcher.profiles()),
            last_event_at=self._last_event_at,
            rejection_reasons=tuple(rejections),
            metadata={
                "pending_count": len(self._queue),
                "retained_rejected_count": len(self._rejected),
                "rejection_rate": rejection_rate,
                "dispatch_error_rate": dispatch_error_rate,
            },
        )
