from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from .buffered_export_pipeline import BufferedExportPipeline
from .export_buffer_repository import JsonExportBufferRepository
from .export_policy import TraceExportPolicy
from .observability_profile import TraceRecord


class TraceExportPipeline:
    def __init__(
        self,
        *,
        policy: TraceExportPolicy | None = None,
        repository: JsonExportBufferRepository | None = None,
    ) -> None:
        self.policy = policy or TraceExportPolicy()
        self.policy.validate()
        self.repository = repository or JsonExportBufferRepository()
        self.pipeline = BufferedExportPipeline(
            signal_type="TRACE",
            repository=self.repository,
            batch_size=self.policy.batch_size,
            maximum_buffer_size=self.policy.maximum_buffer_size,
            maximum_export_attempts=(
                self.policy.maximum_export_attempts
            ),
            failure_mode=self.policy.failure_mode,
        )

    def enqueue(self, trace: TraceRecord):
        return self.pipeline.enqueue(asdict(trace))

    def flush(
        self,
        exporter: Callable[[tuple[dict, ...]], bool],
    ):
        return self.pipeline.flush(exporter)
