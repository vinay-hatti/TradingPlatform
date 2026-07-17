from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from .buffered_export_pipeline import BufferedExportPipeline
from .export_buffer_repository import JsonExportBufferRepository
from .export_policy import LogExportPolicy
from .observability_profile import StructuredLogRecord


class LogExportPipeline:
    def __init__(
        self,
        *,
        policy: LogExportPolicy | None = None,
        repository: JsonExportBufferRepository | None = None,
    ) -> None:
        self.policy = policy or LogExportPolicy()
        self.policy.validate()
        self.repository = repository or JsonExportBufferRepository()
        self.pipeline = BufferedExportPipeline(
            signal_type="LOG",
            repository=self.repository,
            batch_size=self.policy.batch_size,
            maximum_buffer_size=self.policy.maximum_buffer_size,
            maximum_export_attempts=(
                self.policy.maximum_export_attempts
            ),
            failure_mode=self.policy.failure_mode,
        )

    def enqueue(self, record: StructuredLogRecord):
        return self.pipeline.enqueue(asdict(record))

    def flush(
        self,
        exporter: Callable[[tuple[dict, ...]], bool],
    ):
        return self.pipeline.flush(exporter)
