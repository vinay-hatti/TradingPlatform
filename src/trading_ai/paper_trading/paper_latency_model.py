from __future__ import annotations

from .paper_execution_policy import PaperExecutionPolicy


class PaperLatencyModel:
    def __init__(self, policy: PaperExecutionPolicy | None = None) -> None:
        self.policy = policy or PaperExecutionPolicy()
        self.policy.validate()

    def resolve(self, requested_latency_ms: int | None = None) -> int:
        value = (
            self.policy.default_latency_ms
            if requested_latency_ms is None
            else int(requested_latency_ms)
        )
        return min(
            self.policy.maximum_latency_ms,
            max(self.policy.minimum_latency_ms, value),
        )
