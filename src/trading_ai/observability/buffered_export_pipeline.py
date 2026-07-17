from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from typing import Callable, Iterable

from .export_buffer_repository import JsonExportBufferRepository
from .export_profile import ExportBatchResult, ExportEnvelope


class BufferedExportPipeline:
    def __init__(
        self,
        *,
        signal_type: str,
        repository: JsonExportBufferRepository,
        batch_size: int,
        maximum_buffer_size: int,
        maximum_export_attempts: int,
        failure_mode: str,
    ) -> None:
        self.signal_type = signal_type
        self.repository = repository
        self.batch_size = batch_size
        self.maximum_buffer_size = maximum_buffer_size
        self.maximum_export_attempts = maximum_export_attempts
        self.failure_mode = failure_mode

    @staticmethod
    def _id(signal_type: str, payload: dict, at: str) -> str:
        raw = f"{signal_type}:{payload}:{at}"
        return "export-" + hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()[:20]

    def enqueue(self, payload: dict) -> ExportEnvelope:
        if self.repository.count(self.signal_type) >= (
            self.maximum_buffer_size
        ):
            raise RuntimeError(
                f"{self.signal_type} export buffer is full"
            )
        now = datetime.now(timezone.utc).isoformat()
        envelope = ExportEnvelope(
            envelope_id=self._id(
                self.signal_type, payload, now
            ),
            signal_type=self.signal_type,
            payload=payload,
            created_at=now,
            updated_at=now,
        )
        return self.repository.save(envelope)

    def enqueue_many(
        self,
        payloads: Iterable[dict],
    ) -> tuple[ExportEnvelope, ...]:
        return tuple(self.enqueue(payload) for payload in payloads)

    def flush(
        self,
        exporter: Callable[[tuple[dict, ...]], bool],
    ) -> ExportBatchResult:
        pending = self.repository.pending(
            self.signal_type,
            self.batch_size,
        )
        if not pending:
            return ExportBatchResult(
                signal_type=self.signal_type,
                attempted=0,
                exported=0,
                retained=0,
                dropped=0,
                success=True,
            )

        payloads = tuple(item.payload for item in pending)
        try:
            success = bool(exporter(payloads))
            error = None if success else "EXPORTER_RETURNED_FALSE"
        except BaseException as exc:
            success = False
            error = f"{type(exc).__name__}:{exc}"

        exported = retained = dropped = 0
        for envelope in pending:
            if success:
                self.repository.delete(envelope.envelope_id)
                exported += 1
                continue
            attempts = envelope.attempt_count + 1
            if (
                self.failure_mode == "DROP"
                or attempts >= self.maximum_export_attempts
            ):
                self.repository.delete(envelope.envelope_id)
                dropped += 1
            else:
                self.repository.save(replace(
                    envelope,
                    attempt_count=attempts,
                    updated_at=datetime.now(
                        timezone.utc
                    ).isoformat(),
                    last_error=error,
                ))
                retained += 1

        return ExportBatchResult(
            signal_type=self.signal_type,
            attempted=len(pending),
            exported=exported,
            retained=retained,
            dropped=dropped,
            success=success,
            error=error,
        )
